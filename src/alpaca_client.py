from datetime import datetime, timedelta, timezone

import pandas as pd
from alpaca.data.historical.crypto import CryptoHistoricalDataClient
from alpaca.data.requests import CryptoBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import MarketOrderRequest


class AlpacaGateway:
    def __init__(self, api_key: str, api_secret: str, paper: bool = True):
        self.trading = TradingClient(api_key, api_secret, paper=paper)
        self.data = CryptoHistoricalDataClient(api_key, api_secret)

    def account_equity(self) -> float:
        account = self.trading.get_account()
        return float(account.equity)

    def get_crypto_bars(self, symbol: str, timeframe_minutes: int, lookback_bars: int) -> pd.DataFrame:
        end = datetime.now(timezone.utc)
        start = end - timedelta(minutes=timeframe_minutes * (lookback_bars + 5))
        tf = self._resolve_timeframe(timeframe_minutes)
        req = CryptoBarsRequest(symbol_or_symbols=[symbol], timeframe=tf, start=start, end=end)
        bars = self.data.get_crypto_bars(req).df
        if bars.empty:
            return pd.DataFrame(columns=["close"])
        bars = bars.reset_index()
        if "symbol" in bars.columns:
            bars = bars[bars["symbol"] == symbol]
        return bars.sort_values("timestamp").tail(lookback_bars)

    @staticmethod
    def _resolve_timeframe(timeframe_minutes: int) -> TimeFrame:
        if 1 <= timeframe_minutes <= 59:
            return TimeFrame(timeframe_minutes, TimeFrameUnit.Minute)
        if timeframe_minutes % 60 == 0:
            hours = timeframe_minutes // 60
            if 1 <= hours <= 23:
                return TimeFrame(hours, TimeFrameUnit.Hour)
        if timeframe_minutes == 24 * 60:
            return TimeFrame(1, TimeFrameUnit.Day)
        raise ValueError(
            "TIMEFRAME_MINUTES invalido. Usa 1-59 (min), multiplos de 60 hasta 1380 (horas) o 1440 (1 dia)."
        )

    def open_position_qty(self, symbol: str) -> float:
        positions = self.trading.get_all_positions()
        for p in positions:
            if p.symbol == symbol.replace("/", "") or p.symbol == symbol:
                return float(p.qty)
        return 0.0

    def submit_market_buy_notional(self, symbol: str, notional_usd: float) -> str:
        order = MarketOrderRequest(
            symbol=symbol,
            side=OrderSide.BUY,
            time_in_force=TimeInForce.GTC,
            notional=round(notional_usd, 2),
        )
        res = self.trading.submit_order(order)
        return str(res.id)

    def submit_market_sell_qty(self, symbol: str, qty: float) -> str:
        order = MarketOrderRequest(
            symbol=symbol,
            side=OrderSide.SELL,
            time_in_force=TimeInForce.GTC,
            qty=qty,
        )
        res = self.trading.submit_order(order)
        return str(res.id)
