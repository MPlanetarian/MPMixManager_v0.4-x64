@echo off
setlocal
cd /d "%~dp0"

:: 1. Check for modern PowerShell 7 (pwsh.exe) in PATH
set "PS_BIN="
where pwsh.exe >nul 2>&1 && set "PS_BIN=pwsh.exe"

:: 2. Check for standard powershell.exe in PATH
if not defined PS_BIN (
    where powershell.exe >nul 2>&1 && set "PS_BIN=powershell.exe"
)

:: 3. Fallback to hardcoded Windows system paths if PATH is corrupted/missing
if not defined PS_BIN (
    if exist "%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" (
        set "PS_BIN=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
    ) else if exist "%SystemRoot%\SysWOW64\WindowsPowerShell\v1.0\powershell.exe" (
        set "PS_BIN=%SystemRoot%\SysWOW64\WindowsPowerShell\v1.0\powershell.exe"
    )
)

:: 4. Verify an executable was successfully identified
if not defined PS_BIN (
    echo Error: Windows PowerShell executable could not be found at standard system paths.
    pause
    exit /b 1
)

:: 5. Verify manager.ps1 exists in the script directory
if not exist "%~dp0manager.ps1" (
    echo Error: manager.ps1 not found in "%~dp0"
    pause
    exit /b 1
)

:: 6. Execute manager.ps1 and forward all arguments
"%PS_BIN%" -NoProfile -ExecutionPolicy Bypass -File "%~dp0manager.ps1" %*

exit /b %ERRORLEVEL%