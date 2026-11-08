@echo off
setlocal enabledelayedexpansion

:: ==============================================================================
:: MP Liquid Glass Audio Player - Windows Launcher (Windows 10 & 11)
:: Launches the standalone Liquid Glass player with user-configured backend
:: (OpenGL [Default] or Vulkan).
:: ==============================================================================

cd /d "%~dp0\.."
set "BASE_DIR=%CD%"

:: Check for Python
set "PYTHON_BIN="
where python.exe >nul 2>&1 && set "PYTHON_BIN=python.exe"
if not defined PYTHON_BIN (
    where py.exe >nul 2>&1 && set "PYTHON_BIN=py.exe"
)
if not defined PYTHON_BIN (
    for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*" "%ProgramFiles%\Python3*") do (
        if exist "%%~D\python.exe" (
            set "PYTHON_BIN=%%~D\python.exe"
            goto :found_python
        )
    )
)

:found_python
if not defined PYTHON_BIN (
    echo [ERROR] Python was not found in PATH or standard installation folders.
    echo Please install Python 3.10+ from python.org or the Microsoft Store.
    pause
    exit /b 1
)

:: Check config.env for LIQUID_GLASS_BACKEND
set "BACKEND=opengl"
set "CONFIG_FILE=%USERPROFILE%\.config\mix-manager\config.env"
if not exist "%CONFIG_FILE%" set "CONFIG_FILE=%BASE_DIR%\config.env"

if exist "%CONFIG_FILE%" (
    for /f "tokens=1,2 delims==" %%A in ('type "%CONFIG_FILE%" ^| findstr /r "^LIQUID_GLASS_BACKEND="') do (
        set "VAL=%%B"
        set "VAL=!VAL:"=!"
        set "VAL=!VAL:'=!"
        set "VAL=!VAL: =!"
        if not "!VAL!"=="" set "BACKEND=!VAL!"
    )
)

:: Select target script (OpenGL default, or Vulkan if configured)
set "TARGET_PY=%BASE_DIR%\MP_Audio_Player_Liquid_Glass_OpenGL.py"
if /i "%BACKEND%"=="vulkan" (
    if exist "%BASE_DIR%\MP_Audio_Player_Liquid_Glass.py" (
        set "TARGET_PY=%BASE_DIR%\MP_Audio_Player_Liquid_Glass.py"
    )
)

if not exist "%TARGET_PY%" (
    if exist "%BASE_DIR%\MP_Audio_Player_Liquid_Glass_OpenGL.py" (
        set "TARGET_PY=%BASE_DIR%\MP_Audio_Player_Liquid_Glass_OpenGL.py"
    ) else if exist "%BASE_DIR%\MP_Audio_Player_Liquid_Glass.py" (
        set "TARGET_PY=%BASE_DIR%\MP_Audio_Player_Liquid_Glass.py"
    )
)

if not exist "%TARGET_PY%" (
    echo [ERROR] Liquid Glass player script could not be found in "%BASE_DIR%".
    pause
    exit /b 1
)

:: Set environment and execute
set "MP_LIQUID_GLASS=1"
set "MP_LIQUID_GLASS_PLATFORM=win32"
set "PYTHONIOENCODING=utf-8"

:: Automatically start MP Liquid Visualizer with a random preset if not already running
set "VIS_PY=%BASE_DIR%\MP_Liquid_Visualizer.py"
if not exist "%VIS_PY%" set "VIS_PY=%BASE_DIR%\scripts\mp_liquid_visualizer_vulkan.py"
if exist "%VIS_PY%" (
    set "VIS_RUNNING=0"
    for /f "tokens=*" %%P in ('powershell.exe -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*MP_Liquid_Visualizer*' -or $_.CommandLine -like '*mp_liquid_visualizer_vulkan*' } | Select-Object -ExpandProperty ProcessId" 2^>nul') do (
        if not "%%P"=="" set "VIS_RUNNING=1"
    )
    if "!VIS_RUNNING!"=="0" (
        start "" "%PYTHON_BIN%" "%VIS_PY%" --preset random
    )
)

start "" "%PYTHON_BIN%" "%TARGET_PY%" %*
exit /b 0
