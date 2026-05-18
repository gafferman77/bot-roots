@echo off
setlocal
echo Cerrando procesos python del bot (si existen)...
taskkill /F /IM python.exe >nul 2>&1
taskkill /F /IM pythonw.exe >nul 2>&1
echo Listo.
pause
