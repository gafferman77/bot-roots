"""
Cliente de Bybit para trading de futuros USDT perpetuos.
Reemplaza alpaca_client.py en el bot Roots.
"""
import logging
from datetime import datetime, timedelta, timezone

import pandas as pd
from pybit.unified_trading import HTTP


class BybitGateway:
    def __init__(self, api_key: str, api_secret: str, testnet: bool = False):
        self.session = HTTP(
            testnet=testnet,
            api_key=api_key,
            api_secret=api_secret,
        )
        self.symbol = None  # se setea al usarlo

    def account_equity(self) -> float:
        """Retorna el equity total de la cuenta unificada en USDT."""
        try:
            r = self.session.get_wallet_balance(accountType="UNIFIED")
            coins = r["result"]["list"][0]["coin"]
            for coin in coins:
                if coin["coin"] == "USDT":
                    return float(coin["equity"])
            # Si no tiene USDT, intentar con balance total
            return float(r["result"]["list"][0]["totalEquity"])
        except Exception as e:
            logging.error("Error obteniendo equity: %s", e)
            return 0.0

    def get_crypto_bars(self, symbol: str, timeframe_minutes: int, lookback_bars: int) -> pd.DataFrame:
        """Obtiene velas históricas de Bybit."""
        self.symbol = symbol.replace("/", "")  # BTC/USDT -> BTCUSDT

        interval = self._resolve_interval(timeframe_minutes)

        try:
            r = self.session.get_kline(
                category="linear",
                symbol=self.symbol,
                interval=interval,
                limit=min(lookback_bars + 5, 200),
            )
            data = r["result"]["list"]
            if not data:
                return pd.DataFrame(columns=["close"])

            # Bybit retorna [timestamp, open, high, low, close, volume, turnover]
            df = pd.DataFrame(data, columns=["timestamp", "open", "high", "low", "close", "volume", "turnover"])
            df["timestamp"] = pd.to_datetime(df["timestamp"].astype(float), unit="ms", utc=True)
            df["close"] = df["close"].astype(float)
            df["high"]  = df["high"].astype(float)
            df["low"]   = df["low"].astype(float)
            df["open"]  = df["open"].astype(float)
            df["volume"]= df["volume"].astype(float)

            # Bybit retorna en orden descendente, invertir
            df = df.iloc[::-1].reset_index(drop=True)
            return df.tail(lookback_bars)

        except Exception as e:
            logging.error("Error obteniendo barras: %s", e)
            return pd.DataFrame(columns=["close"])

    @staticmethod
    def _resolve_interval(timeframe_minutes: int) -> str:
        """Convierte minutos al formato de intervalo de Bybit."""
        mapping = {
            1: "1", 3: "3", 5: "5", 15: "15", 30: "30",
            60: "60", 120: "120", 240: "240", 360: "360", 720: "720",
            1440: "D",
        }
        if timeframe_minutes in mapping:
            return mapping[timeframe_minutes]
        if timeframe_minutes < 60:
            return str(timeframe_minutes)
        return "60"

    def open_position_qty(self, symbol: str) -> float:
        """Retorna la cantidad de la posición abierta (positivo=long, 0=sin posición)."""
        sym = symbol.replace("/", "")
        try:
            r = self.session.get_positions(
                category="linear",
                symbol=sym,
            )
            positions = r["result"]["list"]
            for p in positions:
                if p["symbol"] == sym and p["side"] == "Buy":
                    return float(p["size"])
            return 0.0
        except Exception as e:
            logging.error("Error obteniendo posicion: %s", e)
            return 0.0

    def get_current_price(self, symbol: str) -> float:
        """Retorna el precio actual de mercado."""
        sym = symbol.replace("/", "")
        try:
            r = self.session.get_tickers(category="linear", symbol=sym)
            return float(r["result"]["list"][0]["lastPrice"])
        except Exception as e:
            logging.error("Error obteniendo precio: %s", e)
            return 0.0

    def set_leverage(self, symbol: str, leverage: int) -> None:
        """Configura el apalancamiento para el símbolo."""
        sym = symbol.replace("/", "")
        try:
            self.session.set_leverage(
                category="linear",
                symbol=sym,
                buyLeverage=str(leverage),
                sellLeverage=str(leverage),
            )
            logging.info("Apalancamiento configurado: %dx para %s", leverage, sym)
        except Exception as e:
            # Puede fallar si ya está configurado — no es crítico
            logging.debug("set_leverage: %s", e)

    def submit_market_buy(self, symbol: str, qty: float) -> str:
        """Abre una posición long con orden de mercado."""
        sym = symbol.replace("/", "")
        try:
            r = self.session.place_order(
                category="linear",
                symbol=sym,
                side="Buy",
                orderType="Market",
                qty=str(round(qty, 6)),
                timeInForce="IOC",
                reduceOnly=False,
            )
            order_id = r["result"]["orderId"]
            logging.info("BUY ejecutado: qty=%.6f | id=%s", qty, order_id)
            return order_id
        except Exception as e:
            logging.error("Error en BUY: %s", e)
            raise

    def submit_market_sell(self, symbol: str, qty: float) -> str:
        """Cierra la posición long con orden de mercado."""
        sym = symbol.replace("/", "")
        try:
            r = self.session.place_order(
                category="linear",
                symbol=sym,
                side="Sell",
                orderType="Market",
                qty=str(round(qty, 6)),
                timeInForce="IOC",
                reduceOnly=True,
            )
            order_id = r["result"]["orderId"]
            logging.info("SELL ejecutado: qty=%.6f | id=%s", qty, order_id)
            return order_id
        except Exception as e:
            logging.error("Error en SELL: %s", e)
            raise
