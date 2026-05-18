from dataclasses import dataclass

import pandas as pd


@dataclass
class Signal:
    action: str  # "buy" | "sell" | "hold"
    reason: str


def rsi(series: pd.Series, period: int) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, 1e-9)
    return 100 - (100 / (1 + rs))


def compute_signal(
    bars: pd.DataFrame,
    ema_fast: int,
    ema_slow: int,
    rsi_period: int,
    rsi_buy_max: float,
    rsi_sell_min: float,
    trend_confirm_bars: int = 3,
) -> Signal:
    if len(bars) < max(ema_slow, rsi_period) + 5:
        return Signal("hold", "No hay suficientes barras")

    close = bars["close"].astype(float)
    ema_f = close.ewm(span=ema_fast, adjust=False).mean()
    ema_s = close.ewm(span=ema_slow, adjust=False).mean()
    rsi_v = rsi(close, rsi_period)

    curr_fast = float(ema_f.iloc[-1])
    curr_slow = float(ema_s.iloc[-1])
    curr_rsi = float(rsi_v.iloc[-1])

    trend_n = max(2, trend_confirm_bars)
    recent = close.tail(trend_n + 1)
    if len(recent) < trend_n + 1:
        return Signal("hold", "Sin suficientes velas para confirmar tendencia")

    diffs = recent.diff().dropna()
    up_streak = bool((diffs > 0).all())
    down_streak = bool((diffs < 0).all())

    if curr_fast > curr_slow and curr_rsi <= rsi_buy_max and up_streak:
        return Signal(
            "buy",
            f"Tendencia alcista EMA{ema_fast}>{ema_slow} ({curr_fast:.2f}>{curr_slow:.2f}), RSI={curr_rsi:.2f} y {trend_n} velas alcistas",
        )
    if curr_fast < curr_slow and curr_rsi >= rsi_sell_min and down_streak:
        return Signal(
            "sell",
            f"Tendencia bajista EMA{ema_fast}<{ema_slow} ({curr_fast:.2f}<{curr_slow:.2f}), RSI={curr_rsi:.2f} y {trend_n} velas bajistas",
        )
    return Signal(
        "hold",
        f"Sin confirmacion | EMA{ema_fast}={curr_fast:.2f}, EMA{ema_slow}={curr_slow:.2f}, RSI={curr_rsi:.2f}, velasUp={up_streak}, velasDown={down_streak}",
    )
