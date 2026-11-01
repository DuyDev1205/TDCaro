@echo off
REM Build TDCaro.exe  (ket qua: dist\TDCaro.exe)
cd /d "%~dp0.."
if not exist .venv (
    python -m venv .venv
)
call .venv\Scripts\activate.bat
python -m pip install -q -r requirements.txt
pyinstaller --noconfirm --clean packaging\TDCaro.spec
echo.
echo Xong! File exe: dist\TDCaro.exe
pause
