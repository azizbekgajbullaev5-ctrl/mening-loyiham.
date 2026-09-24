@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"
title Akademik AI va o'xshashlik tahlilchisi
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
set "VENV=backend\.venv"

if exist "%VENV%\Scripts\python.exe" goto run

echo Python qidirilmoqda...
set "PY="
py -3.12 -c "import sys" >nul 2>&1 && set "PY=py -3.12"
if not defined PY (py -3.13 -c "import sys" >nul 2>&1 && set "PY=py -3.13")
if not defined PY (py -3.11 -c "import sys" >nul 2>&1 && set "PY=py -3.11")
if not defined PY (py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1 && set "PY=py -3")
if not defined PY (python -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1 && set "PY=python")
if not defined PY (
  echo.
  echo [XATO] Python 3.11 yoki undan yangi versiya topilmadi.
  echo Python 3.12 ni https://www.python.org/downloads/ saytidan yuklab o'rnating.
  echo O'rnatishda "Add python.exe to PATH" belgisini albatta qo'ying.
  echo.
  pause
  exit /b 1
)

echo Virtual muhit yaratilmoqda (%PY%)...
%PY% -m venv "%VENV%"
if errorlevel 1 (
  echo [XATO] Virtual muhit yaratilmadi.
  pause
  exit /b 1
)

:run
"%VENV%\Scripts\python.exe" run_local.py %*
if errorlevel 1 (
  echo.
  echo Dastur xato bilan to'xtadi. Yuqoridagi xabarni o'qing yoki uni yordam uchun yuboring.
  pause
)
endlocal
