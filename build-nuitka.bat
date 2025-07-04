@echo off
setlocal enabledelayedexpansion

REM ─── Config ───────────────────────────────────────────────────────────────
set APP_NAME=mizban.exe
set ENTRY=mizban.py
set DATA_DIR=clients\frontend
set DIST_DIR=dist\nuitka
set BUILD_DIR=build\nuitka

REM ─── Clean previous builds ─────────────────────────────────────────────────
if exist "%BUILD_DIR%" rmdir /s /q "%BUILD_DIR%"
if exist "%DIST_DIR%" rmdir /s /q "%DIST_DIR%"

REM ─── Build ────────────────────────────────────────────────────────────────
echo 🛠️  Building %APP_NAME% with Nuitka...

python -m nuitka ^
    --standalone ^
    --onefile ^
    --follow-imports ^
    --remove-output ^
    --lto=yes ^
    --assume-yes-for-downloads ^
    --output-dir="%BUILD_DIR%" ^
    --include-data-dir="%DATA_DIR%=clients/frontend" ^
    "%ENTRY%"

REM ─── Move output ──────────────────────────────────────────────────────────
mkdir "%DIST_DIR%" >nul 2>&1
move /y "%BUILD_DIR%\%APP_NAME%" "%DIST_DIR%\%APP_NAME%"

echo.
echo ✅ Nuitka build complete: %DIST_DIR%\%APP_NAME%
dir "%DIST_DIR%\%APP_NAME%"
endlocal
