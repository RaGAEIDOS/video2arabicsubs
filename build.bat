@echo off
title Building Video2ArabicSubs v0.4
echo ============================================
echo  Building Video2ArabicSubs v0.4
echo  Developed by Ragaei Muhammed
echo ============================================
echo.

echo [1/4] Installing dependencies...
pip install -r requirements-build.txt
if %errorlevel% neq 0 (
    echo FAILED: pip install
    pause
    exit /b 1
)

echo [2/4] Building executable (onedir) with PyInstaller...
pyinstaller --clean video2arabicsubs.spec
if %errorlevel% neq 0 (
    echo FAILED: PyInstaller
    pause
    exit /b 1
)

echo [3/4] Preparing installer icon (optional)...
where magick >nul 2>nul && magick img\first-logo-design.png -resize 256x256 img\app.ico
if not exist img\app.ico (
    where convert >nul 2>nul && convert img\first-logo-design.png -resize 256x256 img\app.ico
)

echo [4/4] Building Windows installer with NSIS (optional)...
where makensis >nul 2>nul
if %errorlevel% equ 0 (
    makensis installer.nsi
    if %errorlevel% neq 0 (
        echo FAILED: makensis
        pause
        exit /b 1
    )
    echo Output: dist\Video2ArabicSubs-Setup-0.4.exe
) else (
    echo makensis not found - installer skipped (app is in dist\Video2ArabicSubs\)
)

echo.
echo Output: dist\Video2ArabicSubs\Video2ArabicSubs.exe
echo.
pause
