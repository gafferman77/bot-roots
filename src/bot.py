import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from .alpaca_client import AlpacaGateway
from .config import Settings
from .risk import RiskLimits, can_trade_today, compute_order_notional, pct_change
from .strategy import compute_signal
from . import server as _srv


class TraderBot:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.gateway = AlpacaGateway(settings.api_key, settings.api_secret, paper=True)
        self.day_start_equity: float | None = None
        self.challenge_start_equity: float | None = None
        self.day_key: str = ""
        self.trades_today = 0
        self.logs_dir = Path(__file__).resolve().parent.parent / "logs"
        self.logs_dir.mkdir(exist_ok=True)
        self.trades_file = self.logs_dir / "trades.jsonl"
        self.status_file = self.logs_dir / "status.json"
        self.last_order_side = "none"
        self.last_order_id = ""

        self.position_file = self.logs_dir / "position.json"
        self.entry_price: float | None = None
        self.entry_qty: float = 0.0
        self._load_position()

    def _load_position(self) -> None:
        if self.position_file.exists():
            try:
                data = json.loads(self.position_file.read_text(encoding="utf-8"))
                self.entry_price = data.get("entry_price")
                self.entry_qty   = data.get("entry_qty", 0.0)
                if self.entry_price:
                    logging.info(
                        "Posicion cargada desde disco: precio=%.2f qty=%.6f",
                        self.entry_price, self.entry_qty
                    )
            except Exception:
                self.entry_price = None
                self.entry_qty   = 0.0

    def _save_position(self) -> None:
        try:
            self.position_file.write_text(
                json.dumps({"entry_price": self.entry_price, "entry_qty": self.entry_qty}),
                encoding="utf-8"
            )
        except Exception:
            pass

    def _clear_position(self) -> None:
        self.entry_price = None
        self.entry_qty   = 0.0
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
            logging.info("Nuevo dia de trading UTC. Equity inicial: %.2f", equity)

    def _append_trade_log(self, payload: dict) -> None:
        # Guardar en memoria para el servidor HTTP
        _srv.append_trade(payload)
        # Intentar guardar en disco también (puede fallar en Render free)
        try:
            with self.trades_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps(payload, ensure_ascii=True) + "\n")
        except Exception:
            pass

    def _write_status(
        self,
        *,
        equity: float,
        day_pct: float,
        day_usd: float,
        total_usd: float,
        signal_action: str,
        signal_reason: str,
        position_qty: float,
        message: str,
        entry_price: float | None = None,
        sl_price: float | None = None,
        tp_price: float | None = None,
    ) -> None:
        status = {
            "ts":               datetime.utcnow().isoformat(),
            "symbol":           self.settings.symbol,
            "equity":           round(equity, 2),
            "day_pct":          round(day_pct, 4),
            "day_usd":          round(day_usd, 2),
            "total_usd":        round(total_usd, 2),
            "trades_today":     self.trades_today,
            "signal_action":    signal_action,
            "signal_reason":    signal_reason,
            "position_qty":     round(position_qty, 8),
            "last_order_side":  self.last_order_side,
            "last_order_id":    self.last_order_id,
            "message":          message,
            "is_profit":        total_usd >= 0,
            "entry_price":      round(entry_price, 2) if entry_price else None,
            "sl_price":         round(sl_price, 2)    if sl_price    else None,
            "tp_price":         round(tp_price, 2)    if tp_price    else None,
        }
        # Actualizar memoria compartida con el servidor HTTP
        _srv.update_status(status)
        # Intentar guardar en disco también
        try:
            self.status_file.write_text(
                json.dumps(status, ensure_ascii=True, indent=2), encoding="utf-8"
            )
        except Exception:
            pass

    def _is_trading_hour(self) -> tuple[bool, str]:
        hora_arg = (datetime.now(timezone.utc).hour - 3) % 24
        if 2 <= hora_arg < 7:
            return False, f"Fuera de horario operativo (hora AR: {hora_arg:02d}:xx)"
        return True, "OK"

    def _check_sl_tp(
        self,
        position_qty: float,
        current_price: float,
        equity: float,
        day_pct: float,
        day_usd: float,
        total_usd: float,
    ) -> bool:
        if not self.entry_price or position_qty <= 0:
            return False

        sl_pct = self.settings.stop_loss_pct   / 100.0
        tp_pct = self.settings.take_profit_pct / 100.0

        sl_price = self.entry_price * (1 - sl_pct)
        tp_price = self.entry_price * (1 + tp_pct)

        hit_sl = current_price <= sl_price
        hit_tp = current_price >= tp_price

        if not hit_sl and not hit_tp:
            return False

        reason = (
            f"STOP-LOSS tocado ({current_price:.2f} <= {sl_price:.2f})"
            if hit_sl else
            f"TAKE-PROFIT tocado ({current_price:.2f} >= {tp_price:.2f})"
        )
        logging.warning(reason)

        order_id = self.gateway.submit_market_sell_qty(self.settings.symbol, position_qty)
        self.trades_today     += 1
        self.last_order_side   = "sell"
        self.last_order_id     = order_id

        self._append_trade_log({
            "ts":        datetime.utcnow().isoformat(),
            "symbol":    self.settings.symbol,
            "side":      "sell",
            "trigger":   "stop_loss" if hit_sl else "take_profit",
            "order_id":  order_id,
            "entry_price": round(self.entry_price, 2),
            "exit_price":  round(current_price, 2),
            "equity":    round(equity, 2),
            "day_pct":   round(day_pct, 4),
            "day_usd":   round(day_usd, 2),
            "total_usd": round(total_usd, 2),
            "reason":    reason,
        })

        self._clear_position()
        self._write_status(
            equity=equity, day_pct=day_pct, day_usd=day_usd, total_usd=total_usd,
            signal_action="sell", signal_reason=reason,
            position_qty=0.0, message=reason,
        )
        return True

    def run_once(self) -> None:
        equity = self.gateway.account_equity()
        if self.challenge_start_equity is None:
            self.challenge_start_equity = equity
        self._roll_day_if_needed(equity)

        assert self.day_start_equity is not None
        assert self.challenge_start_equity is not None

        day_pct   = pct_change(self.day_start_equity, equity)
        day_usd   = equity - self.day_start_equity
        total_usd = equity - self.challenge_start_equity

        limits = RiskLimits(
            risk_per_trade_pct=self.settings.risk_per_trade_pct,
            max_trades_per_day=self.settings.max_trades_per_day,
            daily_stop_pct=self.settings.daily_stop_pct,
            target_daily_usd=self.settings.target_daily_usd,
            target_total_usd=self.settings.target_total_usd,
        )

        position_qty = self.gateway.open_position_qty(self.settings.symbol)

        bars = self.gateway.get_crypto_bars(
            symbol=self.settings.symbol,
            timeframe_minutes=self.settings.timeframe_minutes,
            lookback_bars=self.settings.lookback_bars,
        )
        current_price = float(bars["close"].iloc[-1]) if not bars.empty else 0.0

        if position_qty > 0 and current_price > 0:
            sl_price = self.entry_price * (1 - self.settings.stop_loss_pct / 100) if self.entry_price else None
            tp_price = self.entry_price * (1 + self.settings.take_profit_pct / 100) if self.entry_price else None
            exited = self._check_sl_tp(position_qty, current_price, equity, day_pct, day_usd, total_usd)
            if exited:
                return
        else:
            sl_price = None
            tp_price = None

        can_hour, hour_reason = self._is_trading_hour()
        if not can_hour:
            logging.info("Filtro horario: %s", hour_reason)
            self._write_status(
                equity=equity, day_pct=day_pct, day_usd=day_usd, total_usd=total_usd,
                signal_action="hold", signal_reason=hour_reason,
                position_qty=position_qty,
                message=f"Esperando horario: {hour_reason}",
                entry_price=self.entry_price, sl_price=sl_price, tp_price=tp_price,
            )
            return

        can_trade, reason = can_trade_today(self.trades_today, day_pct, day_usd, total_usd, limits)
        if not can_trade:
            logging.warning("Sin operacion: %s", reason)
            self._write_status(
                equity=equity, day_pct=day_pct, day_usd=day_usd, total_usd=total_usd,
                signal_action="hold", signal_reason=reason,
                position_qty=position_qty,
                message=f"Pausa por riesgo: {reason}",
                entry_price=self.entry_price, sl_price=sl_price, tp_price=tp_price,
            )
            return

        signal = compute_signal(
            bars=bars,
            ema_fast=self.settings.ema_fast,
            ema_slow=self.settings.ema_slow,
            rsi_period=self.settings.rsi_period,
            rsi_buy_max=self.settings.rsi_buy_max,
            rsi_sell_min=self.settings.rsi_sell_min,
            trend_confirm_bars=self.settings.trend_confirm_bars,
        )
        logging.info("Signal %s | %s", signal.action, signal.reason)

        if signal.action == "hold":
            self._write_status(
                equity=equity, day_pct=day_pct, day_usd=day_usd, total_usd=total_usd,
                signal_action=signal.action, signal_reason=signal.reason,
                position_qty=position_qty,
                message="Sin entrada confirmada",
                entry_price=self.entry_price, sl_price=sl_price, tp_price=tp_price,
            )
            return

        order_id = ""
        side     = ""

        if signal.action == "buy" and position_qty <= 0:
            notional = compute_order_notional(equity, self.settings.risk_per_trade_pct)
            order_id = self.gateway.submit_market_buy_notional(self.settings.symbol, notional)
            side     = "buy"
            self.entry_price = current_price
            self.entry_qty   = notional / current_price if current_price > 0 else 0
            self._save_position()
            sl_price = current_price * (1 - self.settings.stop_loss_pct   / 100)
            tp_price = current_price * (1 + self.settings.take_profit_pct / 100)
            logging.info(
                "Entrada BUY | precio=%.2f | SL=%.2f | TP=%.2f",
                current_price, sl_price, tp_price
            )

        elif signal.action == "sell" and position_qty > 0:
            order_id = self.gateway.submit_market_sell_qty(self.settings.symbol, position_qty)
            side     = "sell"
            self._clear_position()
            sl_price = None
            tp_price = None

        else:
            logging.info("No aplica operacion (posicion actual qty=%.6f)", position_qty)
            self._write_status(
                equity=equity, day_pct=day_pct, day_usd=day_usd, total_usd=total_usd,
                signal_action=signal.action, signal_reason=signal.reason,
                position_qty=position_qty,
                message="Senal detectada, pero ya hay posicion en esa direccion",
                entry_price=self.entry_price, sl_price=sl_price, tp_price=tp_price,
            )
            return

        self.trades_today    += 1
        self.last_order_side  = side
        self.last_order_id    = order_id

        trade_log = {
            "ts":          datetime.utcnow().isoformat(),
            "symbol":      self.settings.symbol,
            "side":        side,
            "order_id":    order_id,
            "entry_price": round(current_price, 2) if side == "buy" else None,
            "sl_price":    round(sl_price, 2)       if sl_price     else None,
            "tp_price":    round(tp_price, 2)       if tp_price     else None,
            "equity":      round(equity, 2),
            "day_pct":     round(day_pct, 4),
            "day_usd":     round(day_usd, 2),
            "total_usd":   round(total_usd, 2),
            "reason":      signal.reason,
        }
        self._append_trade_log(trade_log)
        logging.warning("ORDER %s enviada | id=%s", side.upper(), order_id)

        self._write_status(
            equity=equity, day_pct=day_pct, day_usd=day_usd, total_usd=total_usd,
            signal_action=signal.action, signal_reason=signal.reason,
            position_qty=position_qty,
            message=f"Operacion {side.upper()} enviada",
            entry_price=self.entry_price, sl_price=sl_price, tp_price=tp_price,
        )
