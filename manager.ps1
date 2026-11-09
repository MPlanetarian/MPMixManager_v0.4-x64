<#
.SYNOPSIS
    MP_Mix_Manager_v0.3 - Windows PowerShell Launcher
.DESCRIPTION
    Launches MP Mix Archive Manager within Git Bash, MSYS2, or WSL2.
#>

$ErrorActionPreference = "Stop"
$Dir = Split-Path -Parent $MyInvocation.MyCommand.Definition
if (-not $Dir) { $Dir = (Get-Location).Path }
Set-Location $Dir
$UnixDir = $Dir.Replace('\', '/')

# Detect Bash: Git/MSYS2 paths first, then PATH (excluding WindowsApps)
$Bash = @("$env:ProgramFiles\Git\bin\bash.exe", "${env:ProgramFiles(x86)}\Git\bin\bash.exe", "$env:LOCALAPPDATA\Programs\Git\bin\bash.exe", "C:\msys64\usr\bin\bash.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $Bash) { $Bash = (Get-Command bash.exe -All -ErrorAction SilentlyContinue | Where-Object { $_.Source -notmatch 'WindowsApps' } | Select-Object -First 1).Source }

# Setup Environment: Python PATH & Encoding.
# Skip the Microsoft Store alias. A real interpreter (Anaconda, python.org, py -3)
# has to come first or the launchers call the Store stub.
$env:PYTHONIOENCODING = "utf-8"
$pythonHomes = @(
    "$env:ProgramFiles\Python312",
    "$env:LOCALAPPDATA\Programs\Python\Python312",
    "$env:USERPROFILE\miniconda3",
    "$env:USERPROFILE\anaconda3",
    "$env:LOCALAPPDATA\anaconda3",
    "$env:ProgramData\anaconda3"
)
foreach ($pythonHome in $pythonHomes) {
    if (Test-Path -LiteralPath (Join-Path $pythonHome "python.exe")) {
        $env:PATH = "$pythonHome;$pythonHome\Scripts;" + $env:PATH
    }
}

# Shortcuts and the tray belong to this user profile even when install.sh ran
# without a working python3. A failure here must not block the manager.
$integrate = Join-Path $Dir "scripts\windows_user_integration.ps1"
if (Test-Path -LiteralPath $integrate) {
    try {
        $powershellExe = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
        $integrateArgs = "-NoProfile -ExecutionPolicy Bypass -File `"$integrate`" -Root `"$Dir`" -Action Install"
        $info = New-Object System.Diagnostics.ProcessStartInfo
        $info.FileName = $powershellExe
        $info.Arguments = $integrateArgs
        $info.UseShellExecute = $false
        $info.CreateNoWindow = $true
        $info.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
        $proc = [System.Diagnostics.Process]::Start($info)
        $proc.WaitForExit()
        if ($proc.ExitCode -ne 0) {
            Write-Host "[WARNING] Desktop shortcuts or the tray icon were not installed for this user (exit $($proc.ExitCode))." -ForegroundColor Yellow
        }
    } catch {
        Write-Host "[WARNING] Desktop shortcuts or the tray icon could not be installed for this user." -ForegroundColor Yellow
    }
}

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