@echo off
setlocal EnableExtensions
rem Real python.exe for the Windows launchers. The Microsoft Store alias in
rem WindowsApps is not an interpreter and must not win over Anaconda or py -3.
rem The project venv holds glfw, PyOpenGL, and sounddevice, so it comes first.
set "PYTHON_BIN="

if exist "%~dp0..\venv\Scripts\python.exe" (
    "%~dp0..\venv\Scripts\python.exe" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 8) else 1)" >nul 2>&1
    if not errorlevel 1 for %%I in ("%~dp0..\venv\Scripts\python.exe") do set "PYTHON_BIN=%%~fI"
)
if defined PYTHON_BIN goto :emit

where py.exe >nul 2>&1
if not errorlevel 1 (
    for /f "delims=" %%P in ('py.exe -3 -c "import sys; print(sys.executable)" 2^>nul') do (
        if exist "%%~P" set "PYTHON_BIN=%%~P"
    )
)
if defined PYTHON_BIN goto :emit

for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*" "%ProgramFiles%\Python3*" "%ProgramFiles%\Python\Python3*") do (
    if exist "%%~D\python.exe" set "PYTHON_BIN=%%~D\python.exe"
)
if defined PYTHON_BIN goto :emit

for %%P in (
    "%ProgramData%\anaconda3\python.exe"
    "%USERPROFILE%\anaconda3\python.exe"
    "%USERPROFILE%\miniconda3\python.exe"
    "%LOCALAPPDATA%\anaconda3\python.exe"
    "%LOCALAPPDATA%\miniconda3\python.exe"
    "%ProgramData%\miniconda3\python.exe"
) do (
    if exist "%%~P" set "PYTHON_BIN=%%~P" & goto :emit
)

for /f "delims=" %%P in ('where python.exe 2^>nul') do (
    echo %%P | findstr /I /C:"\WindowsApps\" >nul
    if errorlevel 1 (
        if exist "%%~P" set "PYTHON_BIN=%%~P"
        goto :emit
    )
)

:emit
if not defined PYTHON_BIN (
    endlocal
    exit /b 1
)
endlocal & echo %PYTHON_BIN%& exit /b 0
