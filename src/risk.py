from dataclasses import dataclass


@dataclass
class RiskLimits:
    risk_per_trade_pct: float
    max_trades_per_day: int
    daily_stop_pct: float
    target_daily_usd: float
    target_total_usd: float


def pct_change(start_equity: float, current_equity: float) -> float:
    if start_equity <= 0:
        return 0.0
    return ((current_equity - start_equity) / start_equity) * 100.0


def can_trade_today(
    trades_today: int,
    day_pct: float,
    day_usd: float,
    total_usd: float,
    limits: RiskLimits,
) -> tuple[bool, str]:
    if limits.target_total_usd > 0 and total_usd >= limits.target_total_usd:
        return False, f"Meta total alcanzada ({total_usd:.2f} USD)"
    if limits.target_daily_usd > 0 and day_usd >= limits.target_daily_usd:
        return False, f"Meta diaria alcanzada ({day_usd:.2f} USD)"
    if trades_today >= limits.max_trades_per_day:
        return False, "Maximo de operaciones diarias alcanzado"
    if day_pct <= limits.daily_stop_pct:
        return False, f"Stop diario alcanzado ({day_pct:.2f}%)"
    return True, "OK"


def compute_order_notional(equity: float, risk_per_trade_pct: float) -> float:
    raw = equity * (risk_per_trade_pct / 100.0)
    return max(raw, 25.0)
