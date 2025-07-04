@echo off
setlocal enabledelayedexpansion

REM ─── Config ───────────────────────────────────────────────────────────────
set APP_NAME=mizban
set ENTRY=file_server.py
set DATA_DIR=clients\frontend
set DIST_DIR=dist\pyinstaller

REM ─── Clean previous builds ─────────────────────────────────────────────────
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist "%SPEC_FILE%" del /q "%SPEC_FILE%"

REM ─── Build ────────────────────────────────────────────────────────────────
echo 🛠️  Building %APP_NAME% with PyInstaller...
pyinstaller ^
  --name "%APP_NAME%" ^
  --onefile ^
  --noconfirm ^
  --console ^
  --add-data "%DATA_DIR%;clients/frontend" ^
  "%ENTRY%"

REM ─── Move output ──────────────────────────────────────────────────────────
if exist "%DIST_DIR%" rmdir /s /q "%DIST_DIR%"
mkdir "%DIST_DIR%"
move /y dist\%APP_NAME%.exe "%DIST_DIR%\%APP_NAME%.exe"

echo.
echo ✅ PyInstaller build complete: %DIST_DIR%\%APP_NAME%.exe
dir "%DIST_DIR%\%APP_NAME%.exe"
endlocal
