@echo off
chcp 65001 >nul
title Projeck - Cong ty Co phan Dich vu Dev
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
where python >nul 2>nul
if errorlevel 1 (
  echo Chua cai Python. Tai tai https://www.python.org/downloads/
  echo Khi cai, nho tick o "Add python.exe to PATH".
  pause
  exit /b 1
)
python server.py --open %*
pause
