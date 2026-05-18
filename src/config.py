import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _req(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"Falta variable de entorno: {name}")
    return value


@dataclass(frozen=True)
class Settings:
    api_key: str
    api_secret: str
    api_base_url: str
    symbol: str
    timeframe_minutes: int
    lookback_bars: int
    risk_per_trade_pct: float
    max_trades_per_day: int
    daily_stop_pct: float
    target_daily_usd: float
    target_total_usd: float
    ema_fast: int
    ema_slow: int
    rsi_period: int
    rsi_buy_max: float
    rsi_sell_min: float
    trend_confirm_bars: int
    poll_seconds: int
    log_level: str
    # ── Nuevos: protección por orden ──
    stop_loss_pct: float    # % de caída desde entrada para cortar pérdida
    take_profit_pct: float  # % de suba desde entrada para tomar ganancia

    @staticmethod
    def from_env() -> "Settings":
        return Settings(
            api_key=_req("APCA_API_KEY_ID"),
            api_secret=_req("APCA_API_SECRET_KEY"),
            api_base_url=os.getenv("APCA_API_BASE_URL", "https://paper-api.alpaca.markets"),
            symbol=os.getenv("SYMBOL", "BTC/USD"),
            timeframe_minutes=int(os.getenv("TIMEFRAME_MINUTES", "60")),
            lookback_bars=int(os.getenv("LOOKBACK_BARS", "300")),
            risk_per_trade_pct=float(os.getenv("RISK_PER_TRADE_PCT", "2.0")),
            max_trades_per_day=int(os.getenv("MAX_TRADES_PER_DAY", "3")),
            daily_stop_pct=float(os.getenv("DAILY_STOP_PCT", "-2.5")),
            target_daily_usd=float(os.getenv("TARGET_DAILY_USD", "5")),
            target_total_usd=float(os.getenv("TARGET_TOTAL_USD", "25")),
            ema_fast=int(os.getenv("EMA_FAST", "20")),
            ema_slow=int(os.getenv("EMA_SLOW", "50")),
            rsi_period=int(os.getenv("RSI_PERIOD", "14")),
            rsi_buy_max=float(os.getenv("RSI_BUY_MAX", "55")),   # antes 45 — más señales
            rsi_sell_min=float(os.getenv("RSI_SELL_MIN", "45")), # antes 55 — más señales
            trend_confirm_bars=int(os.getenv("TREND_CONFIRM_BARS", "2")),  # antes 3
            poll_seconds=int(os.getenv("POLL_SECONDS", "300")),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            # Nuevos — valores conservadores para empezar
            stop_loss_pct=float(os.getenv("STOP_LOSS_PCT", "2.0")),
            take_profit_pct=float(os.getenv("TAKE_PROFIT_PCT", "4.0")),
        )
