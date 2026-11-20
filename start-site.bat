@echo off
chcp 65001 >nul
title Galereya Best - local site
cd /d "%~dp0"

echo.
echo   ==========================================
echo      Galereya Best - local site
echo   ==========================================
echo.
echo   [1/3] Building site...
python build.py >nul 2>&1
if errorlevel 1 (
  echo   Build error. Details:
  python build.py
  pause
  exit /b
)
echo         OK
echo   [2/3] Opening browser...
start "" cmd /c "timeout /t 2 >nul & start http://127.0.0.1:8010/ru/"
echo   [3/3] Server is running:
echo.
echo         http://127.0.0.1:8010/ru/
echo         http://127.0.0.1:8010/uz/
echo         http://127.0.0.1:8010/en/
echo.
echo   To stop: close this window.
echo.
python tools\serve.py 8010
pause
