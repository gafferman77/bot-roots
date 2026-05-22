from dataclasses import dataclass

import pandas as pd


@dataclass
class Signal:
    action: str  # "buy" | "sell" | "hold"
    reason: str
    atr: float = 0.0


def rsi(series: pd.Series, period: int) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, 1e-9)
    return 100 - (100 / (1 + rs))


def atr(df: pd.DataFrame, period: int) -> pd.Series:
    """Average True Range."""
    high = df["high"]
    low  = df["low"]
    close_prev = df["close"].shift(1)
    tr = pd.concat([
        high - low,
        (high - close_prev).abs(),
        (low  - close_prev).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def compute_signal(
    bars: pd.DataFrame,
    ema_fast: int,
    ema_slow: int,
    rsi_period: int,
    rsi_buy_max: float,
    rsi_sell_min: float,
    trend_confirm_bars: int = 3,
    atr_period: int = 14,
) -> Signal:
    required = max(ema_slow, rsi_period, atr_period) + 10
    if len(bars) < required:
        return Signal("hold", "No hay suficientes barras", 0.0)

    has_volume = "volume" in bars.columns
    close = bars["close"].astype(float)

    ema_f = close.ewm(span=ema_fast, adjust=False).mean()
    ema_s = close.ewm(span=ema_slow, adjust=False).mean()
    rsi_v = rsi(close, rsi_period)

    # ATR para SL/TP dinámico
    if "high" in bars.columns and "low" in bars.columns:
        atr_v = atr(bars, atr_period)
        curr_atr = float(atr_v.iloc[-1])
    else:
        curr_atr = float(close.std())

    curr_fast = float(ema_f.iloc[-1])
    curr_slow = float(ema_s.iloc[-1])
    curr_rsi  = float(rsi_v.iloc[-1])

    # Confirmación de tendencia con N velas consecutivas
    trend_n = max(2, trend_confirm_bars)
    recent = close.tail(trend_n + 1)
    if len(recent) < trend_n + 1:
        return Signal("hold", "Sin suficientes velas para confirmar tendencia", curr_atr)

    diffs = recent.diff().dropna()
    up_streak   = bool((diffs > 0).all())
    down_streak = bool((diffs < 0).all())

    # Filtro de volumen — el volumen actual debe ser mayor al promedio
    volume_ok = True
    if has_volume:
        vol = bars["volume"].astype(float)
        vol_avg = float(vol.tail(20).mean())
        vol_curr = float(vol.iloc[-1])
        volume_ok = vol_curr > vol_avg * 0.8  # al menos 80% del promedio

    # Señal de compra
    if (curr_fast > curr_slow
            and curr_rsi <= rsi_buy_max
            and up_streak
            and volume_ok):
        return Signal(
            "buy",
            f"EMA{ema_fast}>{ema_slow} ({curr_fast:.0f}>{curr_slow:.0f}), "
            f"RSI={curr_rsi:.1f}, {trend_n} velas alcistas, ATR={curr_atr:.0f}",
            curr_atr,
        )

    # Señal de venta
    if (curr_fast < curr_slow
            and curr_rsi >= rsi_sell_min
            and down_streak
            and volume_ok):
        return Signal(
            "sell",
            f"EMA{ema_fast}<{ema_slow} ({curr_fast:.0f}<{curr_slow:.0f}), "
            f"RSI={curr_rsi:.1f}, {trend_n} velas bajistas, ATR={curr_atr:.0f}",
            curr_atr,
        )

    return Signal(
        "hold",
        f"Sin confirmacion | EMA{ema_fast}={curr_fast:.0f}, EMA{ema_slow}={curr_slow:.0f}, "
        f"RSI={curr_rsi:.1f}, velasUp={up_streak}, velasDown={down_streak}, "
        f"volOK={volume_ok}, ATR={curr_atr:.0f}",
        curr_atr,
    )
