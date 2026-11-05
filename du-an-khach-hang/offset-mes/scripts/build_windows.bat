@echo off
rem Đóng gói Offset MES thành một file OffsetMES.exe cho Windows.
rem Yêu cầu: Python 3.10+ đã cài và có trong PATH.
setlocal
cd /d "%~dp0\.."

echo [1/3] Tao moi truong ao...
python -m venv .build-venv || goto :error
call .build-venv\Scripts\activate.bat || goto :error

echo [2/3] Cai PyInstaller...
python -m pip install --upgrade pip pyinstaller || goto :error

echo [3/3] Dong goi...
rem Không dùng --windowed để cửa sổ dòng lệnh hiện ra (cần cho lệnh create-admin và xem log).
pyinstaller --noconfirm --onefile --name OffsetMES ^
  --add-data "offset_mes\static;offset_mes\static" ^
  run_desktop.py || goto :error

echo.
echo Hoan tat. File ung dung: dist\OffsetMES.exe
echo Du lieu duoc luu tai: %%APPDATA%%\OffsetMES\offset_mes.db
goto :eof

:error
echo.
echo LOI: dong goi that bai. Xem thong bao phia tren.
exit /b 1
