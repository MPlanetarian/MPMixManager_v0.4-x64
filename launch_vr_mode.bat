@echo off
setlocal
cd /d "%~dp0"
if exist "%~dp0scripts\enter_vr_mode.bat" (
    call "%~dp0scripts\enter_vr_mode.bat" %*
) else (
    echo Error: scripts\enter_vr_mode.bat not found.
    pause
    exit /b 1
)
exit /b %ERRORLEVEL%
