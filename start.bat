@echo off
cd /d "%~dp0"
python run_local.py
if errorlevel 1 (
  echo.
  echo Xato yuz berdi. Python o'rnatilmagan bo'lsa: WINDOWS-YORIQNOMA.md, 1-qadam.
  pause
)
