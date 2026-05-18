@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] No existe Python del entorno en .venv
  pause
  exit /b 1
)

echo Iniciando servidor local del panel en http://127.0.0.1:8765/panel.html
start "" "http://127.0.0.1:8765/panel.html"
".venv\Scripts\python.exe" -m http.server 8765
