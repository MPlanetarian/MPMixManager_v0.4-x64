@echo off
setlocal
cd /d "%~dp0"
if exist "%~dp0scripts\launch_mp_gui.bat" (
    call "%~dp0scripts\launch_mp_gui.bat" %*
) else (
    echo Error: scripts\launch_mp_gui.bat not found.
    pause
    exit /b 1
)
exit /b %ERRORLEVEL%
