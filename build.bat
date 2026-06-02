@echo off
title Building Video2ArabicSubs v0.1
echo ============================================
echo  Building Video2ArabicSubs v0.1
echo  Developed by Ragaei Muhammed
echo ============================================
echo.

echo [1/3] Installing dependencies...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo FAILED: pip install
    pause
    exit /b 1
)

echo [2/3] Building executable with PyInstaller...
pyinstaller --clean video2arabicsubs.spec
if %errorlevel% neq 0 (
    echo FAILED: PyInstaller
    pause
    exit /b 1
)

echo [3/3] Done!
echo.
echo Output: dist\Video2ArabicSubs.exe
echo.
pause
