<#
.SYNOPSIS
    MP_Mix_Manager_v0.3 - Windows PowerShell Launcher
.DESCRIPTION
    Launches Mix Archive Manager within Git Bash, MSYS2, or WSL2.
#>

$ErrorActionPreference = "Stop"
$Dir = Split-Path -Parent $MyInvocation.MyCommand.Definition
if (-not $Dir) { $Dir = (Get-Location).Path }
Set-Location $Dir
$UnixDir = $Dir.Replace('\', '/')

# Detect Bash: Git/MSYS2 paths first, then PATH (excluding WindowsApps)
$Bash = @("$env:ProgramFiles\Git\bin\bash.exe", "${env:ProgramFiles(x86)}\Git\bin\bash.exe", "$env:LOCALAPPDATA\Programs\Git\bin\bash.exe", "C:\msys64\usr\bin\bash.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $Bash) { $Bash = (Get-Command bash.exe -All -ErrorAction SilentlyContinue | Where-Object { $_.Source -notmatch 'WindowsApps' } | Select-Object -First 1).Source }

# Setup Environment: Python PATH & Encoding
$env:PYTHONIOENCODING = "utf-8"
$PyPaths = @("$env:LOCALAPPDATA\Programs\Python\Python312", "$env:ProgramFiles\Python312")
foreach ($P in $PyPaths) { if (Test-Path $P) { $env:PATH = "$P;$P\Scripts;$env:PATH" } }

try {
    if ($Bash) {
        & $Bash "$UnixDir/Mix_Archive_Manager.sh" @args
    } elseif (Get-Command wsl.exe -ErrorAction SilentlyContinue) {
        $WslDir = (wsl.exe wslpath -a $UnixDir).Trim()
        & wsl.exe bash -c "cd '$WslDir' && ./Mix_Archive_Manager.sh"
    } else {
        Write-Host "==============================================================================" -ForegroundColor Red
        Write-Host "[ERROR] No compatible Bash environment found!" -ForegroundColor Red
        Write-Host "Please install Git for Windows: https://git-scm.com/download/win" -ForegroundColor Cyan
        Write-Host "==============================================================================" -ForegroundColor Red
        Read-Host "Press [Enter] to exit..."
    }
} catch {
    Write-Host "[ERROR] $_" -ForegroundColor Red
    Read-Host "Press [Enter] to exit..."
}