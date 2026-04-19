@echo off
setlocal
echo ============================================================
echo  EQ Log Parser ^- Build
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
if exist dist\EQLogParser rmdir /s /q dist\EQLogParser

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
echo  Output: dist\EQLogParser\EQLogParser.exe
echo.
echo  To distribute: zip the entire dist\EQLogParser\ folder.
echo  Users can replace resources\spells_us.txt with their own.
echo ============================================================
pause
