@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] No existe .venv\Scripts\python.exe
  echo Ejecuta primero la instalacion del entorno.
  pause
  exit /b 1
)

echo ==========================================
echo   BOT ROOTS - PAPER MODE (BTC/USD)
echo ==========================================
echo Carpeta: %cd%
echo.
echo Este bot SI puede enviar ordenes en ALPACA PAPER.
echo.
set /p CONFIRMAR=Quieres iniciar ahora? (S/N): 
if /I not "%CONFIRMAR%"=="S" (
  echo Cancelado.
  pause
  exit /b 0
)
echo.
set /p ABRIR_DASH=Quieres abrir el dashboard de Alpaca en el navegador? (S/N): 
if /I "%ABRIR_DASH%"=="S" (
  start "" "https://app.alpaca.markets/paper/dashboard/overview"
)
echo.
echo Iniciando bot en esta ventana...
echo Para detener desde aqui: Ctrl + C
echo.

".venv\Scripts\python.exe" -m src.main

echo.
echo Bot finalizado.
pause
