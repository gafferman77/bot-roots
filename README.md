# Bot Roots (Paper Trading) - BTC/USD

Base inicial para un bot de swing en Alpaca usando cuenta paper.

## 1) Requisitos

- Python 3.11+
- Cuenta Alpaca con paper trading habilitado

## 2) Configuracion

1. Copiar `.env.example` a `.env`
2. Completar:
   - `APCA_API_KEY_ID`
   - `APCA_API_SECRET_KEY`

Los parametros iniciales ya estan listos para:

- Activo: `BTC/USD`
- Riesgo por trade: `0.5%`
- Maximo trades por dia: `2`
- Stop diario: `-1.5%`
- Objetivo diario: `0 USD` (desactivado por defecto; usa >0 para activarlo)
- Objetivo total de etapa: `25 USD` (al alcanzarlo, deja de operar)

## 3) Instalacion

```bash
pip install -r requirements.txt
```

## 4) Ejecucion

```bash
python -m src.main
```

## 5) Que hace este MVP

- Descarga barras historicas de cripto desde Alpaca.
- Calcula senal con estrategia base:
  - EMA rapida/lenta
  - RSI para confirmar entradas/salidas
  - Confirmacion por secuencia de velas (`TREND_CONFIRM_BARS`, default 3)
- Envia ordenes market en paper:
  - Compra si hay senal de buy y no hay posicion abierta.
  - Vende si hay senal de sell y hay posicion abierta.
- Aplica freno automatico por riesgo/objetivo:
  - No opera si alcanza stop diario.
  - No opera si alcanza meta diaria (solo si `TARGET_DAILY_USD > 0`).
  - No opera si alcanza meta total (solo si `TARGET_TOTAL_USD > 0`).
- Registra operaciones en `logs/trades.jsonl`.

## 6) Siguientes pasos recomendados

- Agregar backtest con la misma estrategia.
- Agregar stop-loss/take-profit por orden (bracket).
- Agregar dashboard simple de PnL diario y drawdown.
- Agregar filtro horario y de volatilidad.

## Notas

- Esto no garantiza ganancias.
- No usar en real hasta validar en paper varias semanas.
