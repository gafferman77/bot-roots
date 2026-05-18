@echo off
setlocal
cd /d "%~dp0"

echo ==========================================
echo   ESTADO RAPIDO - BOT ROOTS
echo ==========================================
echo.

if exist "logs\trades.jsonl" (
  echo Ultimos 10 trades registrados:
  powershell -Command "Get-Content -Path 'logs\\trades.jsonl' -Tail 10"
) else (
  echo Aun no hay trades en logs\trades.jsonl
)

echo.
echo Abrir dashboard de Alpaca Paper...
start "" "https://app.alpaca.markets/paper/dashboard/overview"
echo.
pause
