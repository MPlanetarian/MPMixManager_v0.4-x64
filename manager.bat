@echo off
rem ==============================================================================
rem MP_Mix_Manager_v0.3 - Windows 10 & 11 Native Launcher
rem Launches Mix_Archive_Manager.sh using Git Bash, MSYS2, or WSL
rem ==============================================================================

setlocal enabledelayedexpansion
reg add "HKCU\Console" /v VirtualTerminalLevel /t REG_DWORD /d 1 /f >nul 2>nul
set "PYTHONIOENCODING=utf-8"

:: Setup Python PATH
for %%P in ("%LOCALAPPDATA%\Programs\Python\Python312" "%ProgramFiles%\Python312") do (
    if exist "%%~P" set "PATH=%%~P;%%~P\Scripts;!PATH!"
)

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"
set "SCRIPT_DIR_UNIX=%SCRIPT_DIR:\=/%"

:: 1. Check Standard Git/MSYS2 Paths
for %%B in ("%ProgramFiles%\Git\bin\bash.exe" "%ProgramFiles(x86)%\Git\bin\bash.exe" "%LOCALAPPDATA%\Programs\Git\bin\bash.exe" "C:\msys64\usr\bin\bash.exe") do (
    if exist "%%~B" (
        "%%~B" "%SCRIPT_DIR_UNIX%Mix_Archive_Manager.sh" %*
        if errorlevel 1 pause
        goto :eof
    )
)

:: 2. Check System PATH (excluding WindowsApps stub)
for /f "delims=" %%b in ('where bash.exe 2^>nul') do (
    echo "%%b" | findstr /i "WindowsApps" >nul
    if errorlevel 1 (
        "%%b" "%SCRIPT_DIR_UNIX%Mix_Archive_Manager.sh" %*
        if errorlevel 1 pause
        goto :eof
    )
)

:: 3. Check WSL
where wsl.exe >nul 2>nul
if %ERRORLEVEL% equ 0 (
    for /f "delims=" %%i in ('wsl.exe wslpath "%SCRIPT_DIR%"') do set "WSL_DIR=%%i"
    wsl.exe bash -c "cd '!WSL_DIR!' && ./Mix_Archive_Manager.sh"
    if errorlevel 1 pause
    goto :eof
)

:: 4. Error
echo ==============================================================================
echo [ERROR] No compatible Bash environment found!
echo.
echo Install Git for Windows: https://git-scm.com/download/win
echo ==============================================================================
pause