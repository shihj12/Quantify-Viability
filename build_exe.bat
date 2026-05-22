@echo off
REM Build the standalone Windows app into dist\QuantifyViability\
setlocal

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: .venv not found. Create it first:
    echo     py -V:3.13 -m venv .venv
    echo     .venv\Scripts\python -m pip install -r requirements.txt
    exit /b 1
)

echo Building QuantifyViability.exe ...
.venv\Scripts\python.exe -m PyInstaller quantify_viability.spec --noconfirm
if errorlevel 1 (
    echo.
    echo Build FAILED.
    exit /b 1
)

echo.
echo Build complete:  dist\QuantifyViability\QuantifyViability.exe
echo Zip the dist\QuantifyViability folder to share it.
endlocal
