<#
.SYNOPSIS
    Install MP Mix Manager for the signed-in Windows user.

Shortcuts go on that user's Desktop and Start Menu, never on the Public
desktop. The notification icon is started in this session and again at logon.
Python is not required.
#>
param(
    [Parameter(Mandatory = $true)]
    [string]$Root,
    [ValidateSet("Install", "EnsureTray", "Status")]
    [string]$Action = "Install"
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "windows_liquid_glass_icon.ps1")

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

function Test-MpPublicDesktop {
    param([string]$Path)
    if (-not $Path) { return $false }
    $norm = $Path.Replace("/", "\").TrimEnd("\").ToLowerInvariant()
    return $norm.EndsWith("\users\public\desktop")
}

function Expand-MpShellPath {
    param([string]$Raw, [string]$Profile)
    if (-not $Raw) { return "" }
    $value = $Raw.Replace("%USERPROFILE%", $Profile).Replace("%userprofile%", $Profile)
    return [Environment]::ExpandEnvironmentVariables($value).Trim()
}

function Get-MpInteractiveContext {
    # An elevated installer can be a different account from the person sitting
    # at the desktop. The shortcuts belong to the user who owns explorer.exe.
    $currentSid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
    $chosenSid = $currentSid
    $chosenProfile = $env:USERPROFILE
    try {
        $found = @()
        $explorers = @(Get-CimInstance Win32_Process -Filter "Name = 'explorer.exe'" -ErrorAction SilentlyContinue)
        foreach ($proc in $explorers) {
            try {
                $owner = Invoke-CimMethod -InputObject $proc -MethodName GetOwner
            } catch {
                continue
            }
            if ($owner.ReturnValue -ne 0 -or -not $owner.User) { continue }
            if ($owner.User -match '^(SYSTEM|LOCAL SERVICE|NETWORK SERVICE)$') { continue }
            try {
                $account = New-Object System.Security.Principal.NTAccount("$($owner.Domain)\$($owner.User)")
                $sid = $account.Translate([System.Security.Principal.SecurityIdentifier]).Value
            } catch {
                continue
            }
            $listKey = "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList\$sid"
            if (-not (Test-Path -LiteralPath $listKey)) { continue }
            $profile = [string](Get-ItemProperty -LiteralPath $listKey).ProfileImagePath
            if (-not $profile) { continue }
            $found += [pscustomobject]@{ Sid = $sid; Profile = $profile }
        }
        $match = $found | Where-Object { $_.Sid -eq $currentSid } | Select-Object -First 1
        if ($match) {
            $chosenSid = [string]$match.Sid
            $chosenProfile = [string]$match.Profile
        } elseif ($found.Count -gt 0) {
            $chosenSid = [string]$found[0].Sid
            $chosenProfile = [string]$found[0].Profile
        }
    } catch {
    }
    return [pscustomobject]@{
        Sid = $chosenSid
        Profile = $chosenProfile
        IsCurrent = ($chosenSid -eq $currentSid)
    }
}

function Get-MpRegistryShellFolder {
    param([string]$Sid, [string]$Profile, [string]$ValueName, [string]$Fallback)
    $reg = "Registry::HKEY_USERS\$Sid\Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
    if (Test-Path -LiteralPath $reg) {
        $raw = (Get-Item -LiteralPath $reg).GetValue($ValueName)
        if ($raw) {
            $expanded = Expand-MpShellPath -Raw ([string]$raw) -Profile $Profile
            if ($expanded -and -not (Test-MpPublicDesktop $expanded)) {
                return $expanded
            }
        }
    }
    return Join-Path $Profile $Fallback
}

function Get-MpUserShellFolder {
    param([pscustomobject]$Context, [string]$Kind)
    $valueName = $Kind
    $fallback = switch ($Kind) {
        "Desktop" { "Desktop" }
        "Programs" { "AppData\Roaming\Microsoft\Windows\Start Menu\Programs" }
        "Startup" { "AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup" }
        default { $Kind }
    }
    # DesktopDirectory is the filesystem folder. SpecialFolder.Desktop is the
    # virtual desktop and GetFolderPath often returns an empty string for it.
    if ($Context.IsCurrent) {
        $special = switch ($Kind) {
            "Desktop" { [Environment+SpecialFolder]::DesktopDirectory }
            "Programs" { [Environment+SpecialFolder]::Programs }
            "Startup" { [Environment+SpecialFolder]::Startup }
            default { $null }
        }
        if ($null -ne $special) {
            $live = [Environment]::GetFolderPath($special)
            if ($live -and -not (Test-MpPublicDesktop $live)) {
                return $live
            }
        }
    }
    return Get-MpRegistryShellFolder -Sid $Context.Sid -Profile $Context.Profile -ValueName $valueName -Fallback $fallback
}

function New-MpFolder {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        New-Item -ItemType Directory -Path $Path -Force | Out-Null
    }
}

function Remove-MpStaleShortcut {
    param([string]$Directory)
    if (-not (Test-Path -LiteralPath $Directory)) { return }
    $stale = @(
        "MP_Liquid.lnk",
        "MP Liquid.lnk",
        "MP_Liquid_Glass_Audio_Player.lnk",
        "MP Liquid Glass Audio Player.lnk",
        "Mix_Archive_Manager.lnk",
        "Mix Archive Manager.lnk"
    )
    foreach ($name in $stale) {
        $path = Join-Path $Directory $name
        if (Test-Path -LiteralPath $path) {
            Remove-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue
        }
    }
}

function New-MpShortcut {
    param(
        [string]$Path,
        [string]$Target,
        [string]$Arguments,
        [string]$WorkDir,
        [string]$Description,
        [string]$Icon
    )
    New-MpFolder -Path (Split-Path -Parent $Path)
    $shell = New-Object -ComObject WScript.Shell
    $link = $shell.CreateShortcut($Path)
    $link.TargetPath = $Target
    $link.Arguments = $Arguments
    $link.WorkingDirectory = $WorkDir
    $link.Description = $Description
    if ($Icon -and (Test-Path -LiteralPath $Icon)) {
        $link.IconLocation = "$Icon,0"
    }
    $link.WindowStyle = 1
    $link.Save()
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Shortcut was not created: $Path"
    }
}

function Show-MpDesktopIcons {
    # A shortcut file on Disk is invisible while Explorer's "Show desktop icons"
    # setting is off. Turn that setting on so the four new shortcuts appear.
    $regPath = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced"
    $hidden = 0
    try {
        $hidden = [int](Get-ItemProperty -LiteralPath $regPath -Name HideIcons -ErrorAction Stop).HideIcons
    } catch {
        $hidden = 0
    }
    if ($hidden -ne 1) { return }

    if (-not ("MpDesktopIconToggle" -as [type])) {
        Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public static class MpDesktopIconToggle {
    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    public static extern IntPtr FindWindow(string className, string windowName);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    public static extern IntPtr FindWindowEx(IntPtr parent, IntPtr after, string className, string windowName);
    [DllImport("user32.dll")]
    public static extern IntPtr SendMessage(IntPtr hWnd, uint msg, IntPtr wParam, IntPtr lParam);
}
"@
    }
    $defview = [IntPtr]::Zero
    $progman = [MpDesktopIconToggle]::FindWindow("Progman", "Program Manager")
    if ($progman -ne [IntPtr]::Zero) {
        $defview = [MpDesktopIconToggle]::FindWindowEx($progman, [IntPtr]::Zero, "SHELLDLL_DefView", $null)
    }
    if ($defview -eq [IntPtr]::Zero) {
        $worker = [IntPtr]::Zero
        do {
            $worker = [MpDesktopIconToggle]::FindWindowEx([IntPtr]::Zero, $worker, "WorkerW", $null)
            if ($worker -eq [IntPtr]::Zero) { break }
            $defview = [MpDesktopIconToggle]::FindWindowEx($worker, [IntPtr]::Zero, "SHELLDLL_DefView", $null)
        } while ($defview -eq [IntPtr]::Zero)
    }
    if ($defview -ne [IntPtr]::Zero) {
        # WM_COMMAND 0x7402 toggles "Show desktop icons" and updates HideIcons.
        [MpDesktopIconToggle]::SendMessage($defview, 0x0111, [IntPtr]0x7402, [IntPtr]::Zero) | Out-Null
    } else {
        Set-ItemProperty -LiteralPath $regPath -Name HideIcons -Type DWord -Value 0
    }
    Write-Host "Desktop icons were hidden. They are visible again so the new shortcuts show."
}

function Update-MpDesktopView {
    param([string]$Desktop)
    if (-not ("MpShellNotify" -as [type])) {
        Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public static class MpShellNotify {
    [DllImport("shell32.dll", CharSet = CharSet.Unicode)]
    public static extern void SHChangeNotify(int wEventId, uint uFlags, string dwItem1, System.IntPtr dwItem2);
}
"@
    }
    # SHCNE_UPDATEDIR = 0x1000, SHCNF_PATHW = 0x5, SHCNF_FLUSH = 0x1000
    [MpShellNotify]::SHChangeNotify(0x00001000, 0x1005, $Desktop, [IntPtr]::Zero)
    [MpShellNotify]::SHChangeNotify(0x08000000, 0x1000, $null, [IntPtr]::Zero)
}

function Get-MpTrayProcess {
    foreach ($name in @("powershell.exe", "pwsh.exe")) {
        $procs = @(Get-CimInstance Win32_Process -Filter "Name = '$name'" -ErrorAction SilentlyContinue)
        foreach ($proc in $procs) {
            if ($proc.CommandLine -and $proc.CommandLine -like "*\windows_tray.ps1*") {
                return $proc
            }
        }
    }
    return $null
}

function Start-MpHiddenPowerShell {
    param([string]$Arguments)
    # install.sh runs under Git Bash, which kills child processes when it exits.
    # WMI creates the process in session 0, so the icon never appears on the
    # desktop. Task Scheduler starts it in the signed-in user's session instead.
    $exe = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
    $taskName = "MP Mix Manager Tray Launch"
    $action = New-ScheduledTaskAction -Execute $exe -Argument $Arguments
    $user = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
    $principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
    Register-ScheduledTask -TaskName $taskName -Action $action -Principal $principal -Force | Out-Null
    try {
        Start-ScheduledTask -TaskName $taskName
        $deadline = (Get-Date).AddSeconds(8)
        do {
            if (Get-MpTrayProcess) { break }
            Start-Sleep -Milliseconds 200
        } while ((Get-Date) -lt $deadline)
    } finally {
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
    }
}

function Stop-MpTrayProcess {
    $deadline = (Get-Date).AddSeconds(5)
    do {
        $proc = Get-MpTrayProcess
        if (-not $proc) { return }
        Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
        Start-Sleep -Milliseconds 200
    } while ((Get-Date) -lt $deadline)
}

function Start-MpTray {
    param([string]$InstallRoot, [switch]$Stay)
    $existing = Get-MpTrayProcess
    if ($existing) { return $true }
    $tray = Join-Path $InstallRoot "scripts\windows_tray.ps1"
    if (-not (Test-Path -LiteralPath $tray)) {
        throw "Tray script was not found: $tray"
    }
    $arguments = "-NoProfile -ExecutionPolicy Bypass -STA -WindowStyle Hidden -File `"$tray`" -Root `"$InstallRoot`""
    if ($Stay) { $arguments += " -Stay" }
    Start-MpHiddenPowerShell -Arguments $arguments
    $log = Join-Path $env:USERPROFILE ".config\mix-manager\mp_system_tray.log"
    $deadline = (Get-Date).AddSeconds(12)
    do {
        $proc = Get-MpTrayProcess
        if ($proc -and (Test-Path -LiteralPath $log)) {
            $tail = (Get-Content -LiteralPath $log -Tail 20 -ErrorAction SilentlyContinue) -join "`n"
            if ($tail -match ("ready pid=" + $proc.ProcessId + "\b")) {
                return $true
            }
        }
        Start-Sleep -Milliseconds 200
    } while ((Get-Date) -lt $deadline)
    return $null -ne (Get-MpTrayProcess)
}

function New-MpGuiLauncher {
    param([string]$InstallRoot, [string]$Profile)
    $launchers = Join-Path $Profile ".config\mix-manager\launchers"
    New-MpFolder -Path $launchers
    $cmdPath = Join-Path $launchers "MP Gui.cmd"
    $bat = Join-Path $InstallRoot "launch_mp_gui.bat"
    $content = @"
@echo off
setlocal
call "$bat" %*
exit /b %ERRORLEVEL%
"@
    $utf8 = New-Object System.Text.UTF8Encoding $false
    $text = ($content -replace "`r`n", "`n") -replace "`n", "`r`n"
    [System.IO.File]::WriteAllText($cmdPath, $text, $utf8)
    return $cmdPath
}

function Install-MpUserShortcuts {
    param([string]$InstallRoot)
    $context = Get-MpInteractiveContext
    $desktop = Get-MpUserShellFolder -Context $context -Kind "Desktop"
    $programs = Get-MpUserShellFolder -Context $context -Kind "Programs"
    $startup = Get-MpUserShellFolder -Context $context -Kind "Startup"
    if (Test-MpPublicDesktop $desktop) {
        $desktop = Join-Path $context.Profile "Desktop"
    }
    New-MpFolder -Path $desktop
    $menu = Join-Path $programs "MP Mix Manager"
    New-MpFolder -Path $menu
    New-MpFolder -Path $startup
    Remove-MpStaleShortcut -Directory $desktop
    Remove-MpStaleShortcut -Directory $programs

    $icon = Get-MpLiquidGlassIconPath -InstallRoot $InstallRoot
    $gui = Join-Path $InstallRoot "launch_mp_gui.bat"
    if (-not (Test-Path -LiteralPath $gui)) {
        $gui = New-MpGuiLauncher -InstallRoot $InstallRoot -Profile $context.Profile
    } else {
        New-MpGuiLauncher -InstallRoot $InstallRoot -Profile $context.Profile | Out-Null
    }

    $player = Join-Path $InstallRoot "launch_liquid_glass.bat"
    if (-not (Test-Path -LiteralPath $player)) { $player = Join-Path $InstallRoot "scripts\launch_liquid_glass.bat" }
    $manager = Join-Path $InstallRoot "manager.bat"
    $visualizer = Join-Path $InstallRoot "launch_liquid_visualizer.bat"
    if (-not (Test-Path -LiteralPath $visualizer)) { $visualizer = Join-Path $InstallRoot "scripts\launch_liquid_visualizer.bat" }

    $items = @(
        @{ Name = "MP Liquid Player"; Target = $player; Arguments = ""; Comment = "Launch MP Liquid Player" },
        @{ Name = "MP Mix Manager"; Target = $manager; Arguments = ""; Comment = "Launch MP Mix Manager" },
        @{ Name = "MP Gui"; Target = $gui; Arguments = ""; Comment = "Launch MP Gui" },
        @{ Name = "MP Liquid Visualizer"; Target = $visualizer; Arguments = ""; Comment = "Launch MP Liquid Visualizer" }
    )
    $written = @()
    foreach ($item in $items) {
        if (-not (Test-Path -LiteralPath $item.Target)) {
            throw "Launcher was not found for $($item.Name): $($item.Target)"
        }
        foreach ($dir in @($desktop, $menu)) {
            $linkPath = Join-Path $dir ($item.Name + ".lnk")
            New-MpShortcut -Path $linkPath -Target $item.Target -Arguments $item.Arguments -WorkDir $InstallRoot -Description $item.Comment -Icon $icon
            if ($dir -eq $desktop) { $written += $linkPath }
        }
    }

    $trayScript = Join-Path $InstallRoot "scripts\windows_tray.ps1"
    $powershell = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
    $trayArgs = "-NoProfile -ExecutionPolicy Bypass -STA -WindowStyle Hidden -File `"$trayScript`" -Root `"$InstallRoot`" -Stay"
    New-MpShortcut -Path (Join-Path $startup "MP Mix Manager Tray.lnk") -Target $powershell -Arguments $trayArgs -WorkDir $InstallRoot -Description "MP Mix Manager tray icon" -Icon $icon

    Update-MpDesktopView -Desktop $desktop
    Show-MpDesktopIcons
    Write-Host "User desktop: $desktop"
    foreach ($path in $written) { Write-Host "Shortcut: $path" }
    Write-Host "Start Menu: $menu"
    Write-Host "Startup: $startup"
    return $context
}

$Root = Resolve-MpRoot $Root
if (-not (Test-Path -LiteralPath $Root)) {
    Write-Host "Install root was not found: $Root"
    exit 1
}

if ($Action -eq "Status") {
    if (Get-MpTrayProcess) { exit 0 }
    exit 1
}

if ($Action -eq "EnsureTray") {
    if (Start-MpTray -InstallRoot $Root) { exit 0 }
    Write-Host "The MP Mix Manager tray icon did not start."
    exit 3
}

$context = Install-MpUserShortcuts -InstallRoot $Root
if ($context.IsCurrent) {
    Stop-MpTrayProcess
    if (-not (Start-MpTray -InstallRoot $Root -Stay)) {
        Write-Host "Desktop shortcuts are on the user profile. The tray icon did not start."
        exit 3
    }
    Write-Host "Tray icon: started"
} else {
    Write-Host "Tray icon: will appear the next time this user signs in ($($context.Profile))"
}
exit 0
