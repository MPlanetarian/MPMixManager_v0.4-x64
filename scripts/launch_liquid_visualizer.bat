@echo off
setlocal enabledelayedexpansion

:: ==============================================================================
:: MP Liquid Visualizer - Windows Launcher (Windows 10 & 11)
:: Launches the 1400x1400 borderless 3D audio-reactive raymarching visualizer.
:: ==============================================================================

cd /d "%~dp0\.."
set "BASE_DIR=%CD%"

:: Check for Python. windows_find_python.cmd skips the Microsoft Store alias.
set "PYTHON_BIN="
for /f "delims=" %%P in ('call "%~dp0windows_find_python.cmd"') do (
    if not defined PYTHON_BIN set "PYTHON_BIN=%%P"
)

if not defined PYTHON_BIN (
    echo [ERROR] Python was not found in PATH or standard installation folders.
    echo Please install Python 3.10+ from python.org or the Microsoft Store.
    pause
    exit /b 1
)

set "TARGET_PY=%BASE_DIR%\MP_Liquid_Visualizer.py"
if not exist "%TARGET_PY%" set "TARGET_PY=%BASE_DIR%\scripts\mp_liquid_visualizer_vulkan.py"

if not exist "%TARGET_PY%" (
    echo [ERROR] MP Liquid Visualizer script could not be found in "%BASE_DIR%".
    pause
    exit /b 1
)

set "MP_LIQUID_VISUALIZER=1"
set "PYTHONIOENCODING=utf-8"

start "" "%PYTHON_BIN%" "%TARGET_PY%" %*
exit /b 0
