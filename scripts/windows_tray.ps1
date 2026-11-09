<#
.SYNOPSIS
    Notification-area icon for MP Mix Manager, MP Gui, and MP Liquid Player.
#>
param(
    [Parameter(Mandatory = $true)]
    [string]$Root,
    [switch]$Stay
)

$ErrorActionPreference = "Stop"

function Resolve-MpRoot {
    param([string]$Path)
    $value = $Path.Trim().Trim('"')
    if ($value -match '^/mnt/([A-Za-z])/(.*)$') {
        $value = "{0}:\{1}" -f $Matches[1].ToUpper(), ($Matches[2] -replace '/', '\')
    } elseif ($value -match '^/([A-Za-z])/(.*)$') {
        $value = "{0}:\{1}" -f $Matches[1].ToUpper(), ($Matches[2] -replace '/', '\')
    }
    return [System.IO.Path]::GetFullPath($value)
}

$Root = Resolve-MpRoot $Root

if ([System.Threading.Thread]::CurrentThread.GetApartmentState() -ne [System.Threading.ApartmentState]::STA) {
    $exe = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
    $arguments = "-NoProfile -ExecutionPolicy Bypass -STA -WindowStyle Hidden -File `"$PSCommandPath`" -Root `"$Root`""
    if ($Stay) { $arguments += " -Stay" }
    $info = New-Object System.Diagnostics.ProcessStartInfo
    $info.FileName = $exe
    $info.Arguments = $arguments
    $info.UseShellExecute = $false
    $info.CreateNoWindow = $true
    $info.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
    [System.Diagnostics.Process]::Start($info) | Out-Null
    exit 0
}

function Write-MpTrayLog {
    param([string]$Message)
    try {
        $dir = Join-Path $env:USERPROFILE ".config\mix-manager"
        if (-not (Test-Path -LiteralPath $dir)) {
            New-Item -ItemType Directory -Path $dir -Force | Out-Null
        }
        $log = Join-Path $dir "mp_system_tray.log"
        [System.IO.File]::AppendAllText($log, "$(Get-Date -Format o) $Message`r`n")
    } catch {
    }
}

$mutex = New-Object System.Threading.Mutex($false, "Local\MPMixManagerTray")
$owned = $false
try {
    $owned = $mutex.WaitOne(0)
} catch [System.Threading.AbandonedMutexException] {
    $owned = $true
}
if (-not $owned) {
    exit 0
}

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

if (-not ("MpWindowFocus" -as [type])) {
    Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public static class MpWindowFocus {
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
    [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern bool BringWindowToTop(IntPtr hWnd);
}
"@
}

function Show-MpWindow {
    param([string]$TitlePart)
    $match = Get-Process | Where-Object {
        $_.MainWindowHandle -ne 0 -and $_.MainWindowTitle -like ("*" + $TitlePart + "*")
    } | Select-Object -First 1
    if (-not $match) { return $false }
    $handle = $match.MainWindowHandle
    if ([MpWindowFocus]::IsIconic($handle)) {
        [MpWindowFocus]::ShowWindow($handle, 9) | Out-Null
    }
    [MpWindowFocus]::ShowWindow($handle, 5) | Out-Null
    [MpWindowFocus]::BringWindowToTop($handle) | Out-Null
    [MpWindowFocus]::SetForegroundWindow($handle) | Out-Null
    return $true
}

function Get-MpCommandLines {
    $rows = @()
    foreach ($proc in @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue)) {
        if ($proc.ProcessId -eq $PID) { continue }
        $command = [string]$proc.CommandLine
        if (-not $command) { continue }
        if ($command -like "*windows_tray.ps1*") { continue }
        if ($command -like "*windows_user_integration.ps1*") { continue }
        $rows += [pscustomobject]@{ ProcessId = $proc.ProcessId; CommandLine = $command }
    }
    return $rows
}

function Test-MpRoleRunning {
    param([string]$Role)
    foreach ($row in @(Get-MpCommandLines)) {
        $command = $row.CommandLine
        switch ($Role) {
            "gui" {
                if ($command -like "*MP_Gui.sh*") { return $true }
                if ($command -like "*MP_Audio_Player_Liquid_Glass*" -and $command -like "*--manager*") { return $true }
            }
            "liquid" {
                if ($command -like "*MP_Audio_Player_Liquid_Glass*" -and $command -notlike "*--manager*") { return $true }
                if ($command -like "*launch_liquid_glass*" -or $command -like "*launch-liquid-glass*") { return $true }
            }
            "manager" {
                if ($command -like "*Mix_Archive_Manager.sh*") { return $true }
                if ($command -like "*manager.ps1*") { return $true }
            }
        }
    }
    return $false
}

function Test-MpSuiteRunning {
    foreach ($role in @("gui", "liquid", "manager")) {
        if (Test-MpRoleRunning $role) { return $true }
    }
    foreach ($row in @(Get-MpCommandLines)) {
        if ($row.CommandLine -like "*MP_Liquid_Visualizer*" -or $row.CommandLine -like "*mp_liquid_visualizer*") {
            return $true
        }
    }
    return $false
}

function Stop-MpSuite {
    foreach ($row in @(Get-MpCommandLines)) {
        $command = $row.CommandLine
        $isMp = $false
        foreach ($needle in @(
            "Mix_Archive_Manager.sh",
            "MP_Gui.sh",
            "MP_Audio_Player",
            "MP_Liquid_Visualizer",
            "mp_liquid_visualizer",
            "launch_liquid_glass",
            "launch-liquid-glass",
            "launch_liquid_visualizer",
            "manager.ps1"
        )) {
            if ($command -like "*$needle*") { $isMp = $true; break }
        }
        if ($isMp) {
            Stop-Process -Id $row.ProcessId -Force -ErrorAction SilentlyContinue
        }
    }
}

function Start-MpRole {
    param([string]$Role)
    $titles = @{
        gui = "MP Mix Manager (Liquid Glass"
        liquid = "MP Audio Player (Liquid Glass"
        manager = "MP Mix Archive Manager"
    }
    if (Show-MpWindow -TitlePart $titles[$Role]) { return }
    $target = $null
    switch ($Role) {
        "gui" { $target = Join-Path $env:USERPROFILE ".config\mix-manager\launchers\MP Gui.cmd" }
        "liquid" { $target = Join-Path $Root "launch_liquid_glass.bat" }
        "manager" { $target = Join-Path $Root "manager.bat" }
    }
    if ($target -and (Test-Path -LiteralPath $target)) {
        Start-Process -FilePath $target -WorkingDirectory $Root | Out-Null
    }
}

$script:busyUntil = [datetime]::MinValue
$script:absentSince = $null
$script:closing = $false

function Register-MpLaunch {
    $script:busyUntil = (Get-Date).AddSeconds(20)
    $script:absentSince = $null
}

function Invoke-MpTrayAction {
    param([string]$ActionId)
    if ($script:closing) { return }
    if ($ActionId -eq "close") {
        $script:closing = $true
        Stop-MpSuite
        [System.Windows.Forms.Application]::Exit()
        return
    }
    $role = switch ($ActionId) {
        "gui" { "gui" }
        "liquid" { "liquid" }
        "manager" { "manager" }
        default { "" }
    }
    if (-not $role) { return }
    Register-MpLaunch
    Start-MpRole -Role $role
}

function New-MpClickHandler {
    param([string]$ActionId)
    return {
        param($sender, $eventArgs)
        Invoke-MpTrayAction $ActionId
    }.GetNewClosure()
}

$script:ownIcon = $false
$icon = $null
$ico = Join-Path $Root "assets\MP_Mix_Manager_Windows_Icon.ico"
if (Test-Path -LiteralPath $ico) {
    try {
        $icon = New-Object System.Drawing.Icon($ico)
        $script:ownIcon = $true
    } catch {
        $icon = $null
    }
}
if (-not $icon) {
    $icon = [System.Drawing.SystemIcons]::Application
}

$notify = $null
$timer = $null
try {
    $notify = New-Object System.Windows.Forms.NotifyIcon
    $notify.Icon = $icon
    $notify.Text = "MP Mix Manager"
    $notify.Visible = $true

    $menu = New-Object System.Windows.Forms.ContextMenuStrip
    $entries = @(
        @{ Id = "gui"; Label = "Launch MP Gui" },
        @{ Id = "liquid"; Label = "Launch MP Liquid Player" },
        @{ Id = "manager"; Label = "Launch MP Mix Manager" },
        @{ Id = "close"; Label = "Close MP Mix Manager (Closes everything)" }
    )
    foreach ($entry in $entries) {
        if ($entry.Id -eq "close") {
            [void]$menu.Items.Add("-")
        }
        $item = $menu.Items.Add([string]$entry.Label)
        $item.Add_Click((New-MpClickHandler -ActionId ([string]$entry.Id))) | Out-Null
    }
    $notify.ContextMenuStrip = $menu
    $notify.Add_MouseUp({
        param($sender, $eventArgs)
        if ($eventArgs.Button -eq [System.Windows.Forms.MouseButtons]::Left) {
            $menu.Show([System.Windows.Forms.Cursor]::Position)
        }
    })

    $timer = New-Object System.Windows.Forms.Timer
    $timer.Interval = 2000
    $timer.Add_Tick({
        if ($Stay -or $script:closing) { return }
        if ((Get-Date) -lt $script:busyUntil) { return }
        if (Test-MpSuiteRunning) {
            $script:absentSince = $null
            return
        }
        if (-not $script:absentSince) {
            $script:absentSince = Get-Date
            return
        }
        if (((Get-Date) - $script:absentSince).TotalSeconds -ge 8) {
            [System.Windows.Forms.Application]::Exit()
        }
    })
    $timer.Start()
    Write-MpTrayLog "ready pid=$PID"
    [System.Windows.Forms.Application]::Run()
} catch {
    Write-MpTrayLog "failed pid=$PID $($_.Exception.Message)"
    exit 1
} finally {
    if ($timer) { $timer.Stop(); $timer.Dispose() }
    if ($notify) {
        $notify.Visible = $false
        $notify.Dispose()
    }
    if ($script:ownIcon -and $icon) { $icon.Dispose() }
    if ($owned) {
        try { $mutex.ReleaseMutex() } catch { }
    }
    $mutex.Dispose()
}
Write-MpTrayLog "exit pid=$PID"
exit 0
