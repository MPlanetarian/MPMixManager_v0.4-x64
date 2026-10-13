@echo off
setlocal
cd /d "%~dp0"

:: 1. Detect Git Bash installation path
if exist "C:\Program Files\Git\bin\bash.exe" (
    set "BASH_PATH=C:\Program Files\Git\bin\bash.exe"
) else if exist "%LOCALAPPDATA%\Programs\Git\bin\bash.exe" (
    set "BASH_PATH=%LOCALAPPDATA%\Programs\Git\bin\bash.exe"
) else (
    where bash.exe >nul 2>&1
    if errorlevel 1 (
        echo Error: Git Bash was not found on your system.
        pause
        exit /b 1
    )
    set "BASH_PATH=bash.exe"
)

:: 2. Execute manager.sh and cleanly close the console window on termination
"%BASH_PATH%" -l "./manager.sh" %*
exit