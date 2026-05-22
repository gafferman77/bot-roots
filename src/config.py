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
    testnet: bool
    symbol: str
    leverage: int
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
    atr_period: int
    atr_sl_multiplier: float
    atr_tp_multiplier: float
    poll_seconds: int
    log_level: str

    @staticmethod
    def from_env() -> "Settings":
        return Settings(
            api_key=_req("BYBIT_API_KEY"),
            api_secret=_req("BYBIT_API_SECRET"),
            testnet=os.getenv("BYBIT_TESTNET", "false").lower() == "true",
            symbol=os.getenv("SYMBOL", "BTC/USDT"),
            leverage=int(os.getenv("LEVERAGE", "2")),
            timeframe_minutes=int(os.getenv("TIMEFRAME_MINUTES", "240")),
            lookback_bars=int(os.getenv("LOOKBACK_BARS", "200")),
            risk_per_trade_pct=float(os.getenv("RISK_PER_TRADE_PCT", "10.0")),
            max_trades_per_day=int(os.getenv("MAX_TRADES_PER_DAY", "2")),
            daily_stop_pct=float(os.getenv("DAILY_STOP_PCT", "-10.0")),
            target_daily_usd=float(os.getenv("TARGET_DAILY_USD", "0.5")),
            target_total_usd=float(os.getenv("TARGET_TOTAL_USD", "3.0")),
            ema_fast=int(os.getenv("EMA_FAST", "9")),
            ema_slow=int(os.getenv("EMA_SLOW", "21")),
            rsi_period=int(os.getenv("RSI_PERIOD", "14")),
            rsi_buy_max=float(os.getenv("RSI_BUY_MAX", "55")),
            rsi_sell_min=float(os.getenv("RSI_SELL_MIN", "45")),
            trend_confirm_bars=int(os.getenv("TREND_CONFIRM_BARS", "3")),
            atr_period=int(os.getenv("ATR_PERIOD", "14")),
            atr_sl_multiplier=float(os.getenv("ATR_SL_MULTIPLIER", "1.5")),
            atr_tp_multiplier=float(os.getenv("ATR_TP_MULTIPLIER", "3.0")),
            poll_seconds=int(os.getenv("POLL_SECONDS", "600")),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )
