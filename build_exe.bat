@echo off
REM Build CaroGame.exe  (ket qua: dist\CaroGame.exe)
cd /d "%~dp0"
if not exist .venv (
    python -m venv .venv
)
call .venv\Scripts\activate.bat
python -m pip install -q -r requirements.txt
pyinstaller --noconfirm --clean CaroGame.spec
echo.
echo Xong! File exe: dist\CaroGame.exe
pause
