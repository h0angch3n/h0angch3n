@echo off
chcp 65001 >nul
title Projeck - chay thu
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
python server.py --demo --port 8090 --open
pause
