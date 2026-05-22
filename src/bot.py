import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from .bybit_client import BybitGateway
from .config import Settings
from .risk import RiskLimits, can_trade_today, pct_change
from .strategy import compute_signal
from . import server as _srv


def compute_order_qty(equity: float, risk_pct: float, price: float, leverage: int) -> float:
    notional = equity * (risk_pct / 100.0) * leverage
    qty = notional / price
    return max(round(qty, 3), 0.001)


class TraderBot:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.gateway = BybitGateway(
            api_key=settings.api_key,
            api_secret=settings.api_secret,
            testnet=settings.testnet,
        )
        self.day_start_equity: float | None = None
        self.challenge_start_equity: float | None = None
        self.day_key: str = ""
        self.trades_today = 0
        self.last_order_side = "none"
        self.last_order_id = ""

        self.logs_dir = Path(__file__).resolve().parent.parent / "logs"
        self.logs_dir.mkdir(exist_ok=True)
        self.position_file = self.logs_dir / "position.json"

        self.entry_price: float | None = None
        self.entry_qty: float = 0.0
        self.sl_price: float | None = None
        self.tp_price: float | None = None

        self._load_position()

        try:
            self.gateway.set_leverage(settings.symbol, settings.leverage)
        except Exception as e:
            logging.warning("No se pudo configurar leverage: %s", e)

    def _load_position(self) -> None:
        if self.position_file.exists():
            try:
                data = json.loads(self.position_file.read_text(encoding="utf-8"))
                self.entry_price = data.get("entry_price")
                self.entry_qty   = data.get("entry_qty", 0.0)
                self.sl_price    = data.get("sl_price")
                self.tp_price    = data.get("tp_price")
                if self.entry_price:
                    logging.info("Posicion cargada desde disco: precio=%.2f qty=%.6f", self.entry_price, self.entry_qty)
                    return
            except Exception:
                pass
        env_price = os.getenv("ENTRY_PRICE", "").strip()
        env_qty   = os.getenv("ENTRY_QTY", "").strip()
        if env_price and env_qty:
            try:
                self.entry_price = float(env_price)
                self.entry_qty   = float(env_qty)
                logging.info("Posicion cargada desde ENV: precio=%.2f qty=%.6f", self.entry_price, self.entry_qty)
            except Exception:
                pass

    def _save_position(self) -> None:
        try:
            self.position_file.write_text(json.dumps({
                "entry_price": self.entry_price,
                "entry_qty":   self.entry_qty,
                "sl_price":    self.sl_price,
                "tp_price":    self.tp_price,
            }), encoding="utf-8")
        except Exception:
            pass

    def _clear_position(self) -> None:
        self.entry_price = None
        self.entry_qty   = 0.0
        self.sl_price    = None
        self.tp_price    = None
        try:
            if self.position_file.exists():
                self.position_file.unlink()
        except Exception:
            pass

    def _roll_day_if_needed(self, equity: float) -> None:
        now_key = datetime.utcnow().strftime("%Y-%m-%d")
        if now_key != self.day_key:
            self.day_key          = now_key
            self.day_start_equity = equity
            self.trades_today     = 0
            logging.info("Nuevo dia UTC. Equity inicial: %.2f", equity)

    def _append_trade(self, payload: dict) -> None:
        _srv.append_trade(payload)
        try:
            trades_file = self.logs_dir / "trades.jsonl"
            with trades_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps(payload) + "\n")
        except Exception:
            pass

    def _write_status(self, *, equity, day_pct, day_usd, total_usd,
                      signal_action, signal_reason, position_qty, message) -> None:
        status = {
            "ts":              datetime.utcnow().isoformat(),
            "symbol":          self.settings.symbol,
            "equity":          round(equity, 2),
            "day_pct":         round(day_pct, 4),
            "day_usd":         round(day_usd, 2),
            "total_usd":       round(total_usd, 2),
            "trades_today":    self.trades_today,
            "signal_action":   signal_action,
            "signal_reason":   signal_reason,
            "position_qty":    round(position_qty, 6),
            "last_order_side": self.last_order_side,
            "last_order_id":   self.last_order_id,
            "message":         message,
            "is_profit":       total_usd >= 0,
            "entry_price":     round(self.entry_price, 2) if self.entry_price else None,
            "sl_price":        round(self.sl_price, 2)    if self.sl_price    else None,
            "tp_price":        round(self.tp_price, 2)    if self.tp_price    else None,
        }
        _srv.update_status(status)
        try:
            (self.logs_dir / "status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _is_trading_hour(self) -> tuple[bool, str]:
        hora_arg = (datetime.now(timezone.utc).hour - 3) % 24
        if 2 <= hora_arg < 7:
            return False, f"Fuera de horario (hora AR: {hora_arg:02d}:xx)"
        return True, "OK"

    def _check_sl_tp(self, current_price, position_qty, equity, day_pct, day_usd, total_usd) -> bool:
        if not self.entry_price or not self.sl_price or not self.tp_price or position_qty <= 0:
            return False

        hit_sl = current_price <= self.sl_price
        hit_tp = current_price >= self.tp_price
        if not hit_sl and not hit_tp:
            return False

        reason = (
            f"STOP-LOSS tocado ({current_price:.2f} <= {self.sl_price:.2f})"
            if hit_sl else
            f"TAKE-PROFIT tocado ({current_price:.2f} >= {self.tp_price:.2f})"
        )
        logging.warning(reason)

        try:
            order_id = self.gateway.submit_market_sell(self.settings.symbol, position_qty)
            pnl = (current_price - self.entry_price) * position_qty * self.settings.leverage
            self.trades_today   += 1
            self.last_order_side = "sell"
            self.last_order_id   = order_id
            self._append_trade({
                "ts": datetime.utcnow().isoformat(),
                "symbol": self.settings.symbol,
                "side": "sell",
                "trigger": "stop_loss" if hit_sl else "take_profit",
                "order_id": order_id,
                "entry_price": round(self.entry_price, 2),
                "exit_price": round(current_price, 2),
                "pnl": round(pnl, 4),
                "equity": round(equity, 2),
                "reason": reason,
            })
            self._clear_position()
            self._write_status(
                equity=equity, day_pct=day_pct, day_usd=day_usd, total_usd=total_usd,
                signal_action="sell", signal_reason=reason,
                position_qty=0.0, message=reason,
            )
        except Exception as e:
            logging.error("Error cerrando posicion: %s", e)
        return True

    def run_once(self) -> None:
        equity = self.gateway.account_equity()
        if not equity:
            logging.warning("No se pudo obtener equity")
            return

        if self.challenge_start_equity is None:
            self.challenge_start_equity = equity
        self._roll_day_if_needed(equity)

        day_pct   = pct_change(self.day_start_equity, equity)
        day_usd   = equity - self.day_start_equity
        total_usd = equity - self.challenge_start_equity

        current_price = self.gateway.get_current_price(self.settings.symbol)
        if not current_price:
            logging.warning("No se pudo obtener precio")
            return

        position_qty = self.gateway.open_position_qty(self.settings.symbol)

        if position_qty > 0 and self.entry_price:
            if not self.sl_price or not self.tp_price:
                bars = self.gateway.get_crypto_bars(
                    self.settings.symbol, self.settings.timeframe_minutes, self.settings.lookback_bars)
                sig = compute_signal(bars, self.settings.ema_fast, self.settings.ema_slow,
                                     self.settings.rsi_period, self.settings.rsi_buy_max,
                                     self.settings.rsi_sell_min, self.settings.trend_confirm_bars,
                                     self.settings.atr_period)
                curr_atr = sig.atr if sig.atr > 0 else current_price * 0.01
                self.sl_price = self.entry_price - (curr_atr * self.settings.atr_sl_multiplier)
                self.tp_price = self.entry_price + (curr_atr * self.settings.atr_tp_multiplier)
                self._save_position()

            exited = self._check_sl_tp(current_price, position_qty, equity, day_pct, day_usd, total_usd)
            if exited:
                return

        can_hour, hour_reason = self._is_trading_hour()
        if not can_hour:
            self._write_status(equity=equity, day_pct=day_pct, day_usd=day_usd, total_usd=total_usd,
                               signal_action="hold", signal_reason=hour_reason,
                               position_qty=position_qty, message=hour_reason)
            return

        limits = RiskLimits(
            risk_per_trade_pct=self.settings.risk_per_trade_pct,
            max_trades_per_day=self.settings.max_trades_per_day,
            daily_stop_pct=self.settings.daily_stop_pct,
            target_daily_usd=self.settings.target_daily_usd,
            target_total_usd=self.settings.target_total_usd,
        )
        can_trade, reason = can_trade_today(self.trades_today, day_pct, day_usd, total_usd, limits)
        if not can_trade:
            logging.warning("Sin operacion: %s", reason)
            self._write_status(equity=equity, day_pct=day_pct, day_usd=day_usd, total_usd=total_usd,
                               signal_action="hold", signal_reason=reason,
                               position_qty=position_qty, message=reason)
            return

        bars = self.gateway.get_crypto_bars(
            self.settings.symbol, self.settings.timeframe_minutes, self.settings.lookback_bars)
        if bars.empty:
            logging.warning("Sin barras disponibles")
            return

        signal = compute_signal(
            bars=bars, ema_fast=self.settings.ema_fast, ema_slow=self.settings.ema_slow,
            rsi_period=self.settings.rsi_period, rsi_buy_max=self.settings.rsi_buy_max,
            rsi_sell_min=self.settings.rsi_sell_min, trend_confirm_bars=self.settings.trend_confirm_bars,
            atr_period=self.settings.atr_period,
        )
        logging.info("Signal %s | %s", signal.action, signal.reason)

        if signal.action == "hold":
            self._write_status(equity=equity, day_pct=day_pct, day_usd=day_usd, total_usd=total_usd,
                               signal_action=signal.action, signal_reason=signal.reason,
                               position_qty=position_qty, message="Sin entrada confirmada")
            return

        if signal.action == "buy" and position_qty <= 0:
            qty = compute_order_qty(equity, self.settings.risk_per_trade_pct, current_price, self.settings.leverage)
            curr_atr = signal.atr if signal.atr > 0 else current_price * 0.01
            try:
                order_id = self.gateway.submit_market_buy(self.settings.symbol, qty)
                self.entry_price = current_price
                self.entry_qty   = qty
                self.sl_price    = current_price - (curr_atr * self.settings.atr_sl_multiplier)
                self.tp_price    = current_price + (curr_atr * self.settings.atr_tp_multiplier)
                self._save_position()
                self.trades_today   += 1
                self.last_order_side = "buy"
                self.last_order_id   = order_id
                self._append_trade({
                    "ts": datetime.utcnow().isoformat(), "symbol": self.settings.symbol,
                    "side": "buy", "order_id": order_id, "entry_price": round(current_price, 2),
                    "sl_price": round(self.sl_price, 2), "tp_price": round(self.tp_price, 2),
                    "qty": qty, "equity": round(equity, 2), "reason": signal.reason,
                })
                logging.warning("BUY | precio=%.2f | SL=%.2f | TP=%.2f | qty=%.4f",
                                current_price, self.sl_price, self.tp_price, qty)
            except Exception as e:
                logging.error("Error en BUY: %s", e)

        elif signal.action == "sell" and position_qty > 0:
            try:
                order_id = self.gateway.submit_market_sell(self.settings.symbol, position_qty)
                pnl = (current_price - (self.entry_price or current_price)) * position_qty * self.settings.leverage
                self._append_trade({
                    "ts": datetime.utcnow().isoformat(), "symbol": self.settings.symbol,
                    "side": "sell", "order_id": order_id, "exit_price": round(current_price, 2),
                    "pnl": round(pnl, 4), "equity": round(equity, 2), "reason": signal.reason,
                })
                self._clear_position()
                self.trades_today   += 1
                self.last_order_side = "sell"
                self.last_order_id   = order_id
                logging.warning("SELL | precio=%.2f | PNL=%.4f", current_price, pnl)
            except Exception as e:
                logging.error("Error en SELL: %s", e)
        else:
            logging.info("Señal %s no aplica (qty=%.4f)", signal.action, position_qty)

        self._write_status(equity=equity, day_pct=day_pct, day_usd=day_usd, total_usd=total_usd,
                           signal_action=signal.action, signal_reason=signal.reason,
                           position_qty=position_qty, message=f"Operacion {self.last_order_side.upper()}")
