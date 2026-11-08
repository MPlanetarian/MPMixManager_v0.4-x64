@echo off
setlocal
cd /d "%~dp0"
if exist "%~dp0scripts\launch_liquid_visualizer.bat" (
    call "%~dp0scripts\launch_liquid_visualizer.bat" %*
) else (
    echo Error: scripts\launch_liquid_visualizer.bat not found.
    pause
    exit /b 1
)
exit /b %ERRORLEVEL%
