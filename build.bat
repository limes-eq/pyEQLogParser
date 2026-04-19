@echo off
setlocal
echo ============================================================
echo  pyEQLogParser ^- Build
echo ============================================================
echo.

where pyinstaller >nul 2>&1
if errorlevel 1 (
    echo PyInstaller not found. Installing...
    pip install pyinstaller
    if errorlevel 1 ( echo pip failed. && pause && exit /b 1 )
)

echo Cleaning previous build...
if exist build rmdir /s /q build
if exist dist\pyEQLogParser rmdir /s /q dist\pyEQLogParser

echo.
echo Running PyInstaller...
pyinstaller eq_parser.spec --clean
if errorlevel 1 (
    echo.
    echo Build FAILED. Check output above for errors.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  Build complete^^!
echo  Output: dist\pyEQLogParser\pyEQLogParser.exe
echo.
echo  To distribute: zip the entire dist\pyEQLogParser\ folder.
echo  Users can replace resources\spells_us.txt with their own.
echo ============================================================
pause
