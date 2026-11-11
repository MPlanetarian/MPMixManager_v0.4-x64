@echo off
setlocal enabledelayedexpansion

:: ==============================================================================
:: MP Liquid Player VR Mode - Windows Launcher (Windows 10 & 11)
:: Starts Bigscreen VR, centers the MP Liquid Player on the primary desktop,
:: then starts the music once the player reports that it is centered.
:: Uses windows_find_python.cmd so the Microsoft Store python3 alias is skipped.
:: ==============================================================================

cd /d "%~dp0\.."
set "BASE_DIR=%CD%"

set "PYTHON_BIN="
for /f "delims=" %%P in ('call "%~dp0windows_find_python.cmd"') do (
    if not defined PYTHON_BIN set "PYTHON_BIN=%%P"
)

if not defined PYTHON_BIN (
    echo [ERROR] Python was not found in PATH or standard installation folders.
    echo The project venv, Python 3.10+, or Anaconda is required.
    pause
    exit /b 1
)

set "VR_PY=%BASE_DIR%\scripts\bigscreen_vr.py"
if not exist "!VR_PY!" (
    echo [ERROR] scripts\bigscreen_vr.py was not found in "%BASE_DIR%".
    pause
    exit /b 1
)

set "MP_VR_MODE=1"
set "MP_HEADER_CLI_MODE=vr"
set "PYTHONIOENCODING=utf-8"

"%PYTHON_BIN%" "!VR_PY!" --root "%BASE_DIR%"
set "VR_RC=%ERRORLEVEL%"
if not "%VR_RC%"=="0" (
    echo.
    echo VR Mode did not start. See %%USERPROFILE%%\.config\mix-manager\vr_mode.log
    pause
)
exit /b %VR_RC%
