@echo off
setlocal
cd /d "%~dp0"
if exist "%~dp0scripts\launch_liquid_glass.bat" (
    call "%~dp0scripts\launch_liquid_glass.bat" %*
) else (
    echo Error: scripts\launch_liquid_glass.bat not found.
    pause
    exit /b 1
)
exit /b %ERRORLEVEL%
