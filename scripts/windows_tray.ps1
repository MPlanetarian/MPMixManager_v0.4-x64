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

function Show-MpTrayButton {
    # A new icon stays in the overflow. Dragging it onto the user notification
    # area keeps it on the taskbar. An icon the user hid is not in the overflow,
    # so it is left there. Each call does one short step and returns, so the
    # notification icon keeps its message pump between steps.
    if (-not ("MpTrayButton" -as [type])) {
        Add-Type -AssemblyName UIAutomationClient
        Add-Type -AssemblyName UIAutomationTypes
        Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
using System.Text;
using Accessibility;
public static class MpTrayButton {
    public delegate bool EnumProc(IntPtr h, IntPtr l);
    [StructLayout(LayoutKind.Sequential)] public struct POINT { public int X, Y; }
    [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
    [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
    [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
    [DllImport("user32.dll")] public static extern bool GetCursorPos(out POINT pt);
    [DllImport("user32.dll")] public static extern void mouse_event(uint flags, uint dx, uint dy, uint data, UIntPtr extra);
    [DllImport("user32.dll")] public static extern IntPtr WindowFromPoint(POINT pt);
    [DllImport("user32.dll")] public static extern IntPtr GetAncestor(IntPtr h, uint flags);
    [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetClassName(IntPtr h, StringBuilder sb, int n);
    [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowText(IntPtr h, StringBuilder sb, int n);
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
    [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc proc, IntPtr l);
    [DllImport("user32.dll")] public static extern bool EnumChildWindows(IntPtr parent, EnumProc proc, IntPtr l);
    [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern IntPtr FindWindow(string cls, string name);
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
    [DllImport("oleacc.dll")] public static extern int AccessibleObjectFromWindow(IntPtr hwnd, uint objid, ref Guid iid, [MarshalAs(UnmanagedType.Interface)] out IAccessible acc);
    public static string LastPlace;
    public static int FoundX;
    public static int FoundY;
    public static int SavedX;
    public static int SavedY;
    public static bool Saved;
    public static void Remember() {
        POINT pt;
        GetCursorPos(out pt);
        SavedX = pt.X;
        SavedY = pt.Y;
        Saved = true;
    }
    public static void Restore() {
        if (Saved) SetCursorPos(SavedX, SavedY);
    }
    static IAccessible Access(IntPtr hwnd) {
        Guid iid = new Guid("618736E0-3C3D-11CF-810C-00AA00389B71");
        IAccessible acc;
        int hr = AccessibleObjectFromWindow(hwnd, 0xFFFFFFFC, ref iid, out acc);
        if (hr != 0) return null;
        return acc;
    }
    public static bool ContainsName(IntPtr hwnd, string name) {
        IAccessible acc = Access(hwnd);
        if (acc == null) return false;
        int count = acc.accChildCount;
        for (int i = 1; i <= count; i++) {
            try { if (acc.get_accName(i) == name) return true; } catch { }
        }
        return false;
    }
    public static bool FindNamed(IntPtr hwnd, string name) {
        FoundX = 0;
        FoundY = 0;
        IAccessible acc = Access(hwnd);
        if (acc == null) return false;
        int count = acc.accChildCount;
        for (int i = 1; i <= count; i++) {
            string item = "";
            try { item = "" + acc.get_accName(i); } catch { continue; }
            if (item != name) continue;
            int l, t, w, h;
            try { acc.accLocation(out l, out t, out w, out h, i); } catch { return false; }
            if (w < 8 || h < 8) return false;
            FoundX = l + (w / 2);
            FoundY = t + (h / 2);
            return true;
        }
        return false;
    }
    public static string Where(int x, int y) {
        POINT pt; pt.X = x; pt.Y = y;
        IntPtr root = GetAncestor(WindowFromPoint(pt), 2);
        var cls = new StringBuilder(80);
        GetClassName(root, cls, 80);
        return cls.ToString();
    }
    public static bool Place(int x, int y) {
        int aimX = x, aimY = y;
        POINT cur;
        for (int i = 0; i < 6; i++) {
            SetCursorPos(aimX, aimY);
            System.Threading.Thread.Sleep(40);
            GetCursorPos(out cur);
            LastPlace = cur.X + "," + cur.Y;
            if (Math.Abs(cur.X - x) <= 2 && Math.Abs(cur.Y - y) <= 2) return true;
            aimX += x - cur.X;
            aimY += y - cur.Y;
        }
        return false;
    }
    public static IntPtr FindVisible(string cls) {
        IntPtr hit = IntPtr.Zero;
        EnumProc proc = delegate(IntPtr h, IntPtr l) {
            var c = new StringBuilder(80);
            GetClassName(h, c, 80);
            if (c.ToString() == cls && IsWindowVisible(h)) { hit = h; return false; }
            return true;
        };
        EnumWindows(proc, IntPtr.Zero);
        GC.KeepAlive(proc);
        return hit;
    }
    public static IntPtr FindChild(IntPtr parent, string cls, string title) {
        IntPtr hit = IntPtr.Zero;
        EnumProc proc = delegate(IntPtr h, IntPtr l) {
            var c = new StringBuilder(80);
            var t = new StringBuilder(160);
            GetClassName(h, c, 80);
            GetWindowText(h, t, 160);
            if (c.ToString() == cls && (title == null || t.ToString() == title)) { hit = h; return false; }
            return true;
        };
        EnumChildWindows(parent, proc, IntPtr.Zero);
        GC.KeepAlive(proc);
        return hit;
    }
}
"@ -ReferencedAssemblies Accessibility
    }
    [MpTrayButton]::SetProcessDPIAware() | Out-Null
    if (-not $script:trayPromote) {
        $script:trayPromote = @{ Phase = "look"; Tries = 0; ChevronX = 0; ChevronY = 0 }
        [MpTrayButton]::Remember()
    }
    $step = $script:trayPromote
    $shell = [MpTrayButton]::FindWindow("Shell_TrayWnd", $null)
    $pager = [MpTrayButton]::FindChild($shell, "SysPager", $null)
    $promoted = [MpTrayButton]::FindChild($pager, "ToolbarWindow32", "User Promoted Notification Area")
    if ($promoted -eq [IntPtr]::Zero) { throw "taskbar notification area was not found" }
    if ([MpTrayButton]::ContainsName($promoted, "MP Mix Manager")) {
        if ($step.Phase -eq "look") {
            Write-MpTrayLog "promoted already"
        } else {
            Close-MpOverflowChevron -X $step.ChevronX -Y $step.ChevronY
            Write-MpTrayLog "promoted"
        }
        [MpTrayButton]::Restore()
        return $true
    }
    switch ($step.Phase) {
        "look" {
            $root = [System.Windows.Automation.AutomationElement]::RootElement
            $trayCond = New-Object System.Windows.Automation.PropertyCondition ([System.Windows.Automation.AutomationElement]::ClassNameProperty, "Shell_TrayWnd")
            $tray = $root.FindFirst([System.Windows.Automation.TreeScope]::Children, $trayCond)
            $idCond = New-Object System.Windows.Automation.PropertyCondition ([System.Windows.Automation.AutomationElement]::AutomationIdProperty, "1502")
            $chevron = $null
            if ($tray) { $chevron = $tray.FindFirst([System.Windows.Automation.TreeScope]::Descendants, $idCond) }
            if (-not $chevron) { throw "overflow button was not found" }
            $chevRect = $chevron.Current.BoundingRectangle
            $step.ChevronX = [int]($chevRect.X + ($chevRect.Width / 2))
            $step.ChevronY = [int]($chevRect.Y + ($chevRect.Height / 2))
            if ([MpTrayButton]::Where($step.ChevronX, $step.ChevronY) -ne "Shell_TrayWnd") { throw "overflow button is covered" }
            $overflow = [MpTrayButton]::FindVisible("NotifyIconOverflowWindow")
            if ($overflow -eq [IntPtr]::Zero) {
                if (-not (Invoke-MpTrayClick -X $step.ChevronX -Y $step.ChevronY -ExpectedClass "Shell_TrayWnd")) {
                    throw "could not reach the overflow button"
                }
            }
            $step.Phase = "seek"
            return $false
        }
        "seek" {
            $step.Tries++
            $overflow = [MpTrayButton]::FindVisible("NotifyIconOverflowWindow")
            if ($overflow -eq [IntPtr]::Zero) {
                if ($step.Tries -ge 4) { throw "overflow did not open" }
                return $false
            }
            $bar = [MpTrayButton]::FindChild($overflow, "ToolbarWindow32", "Overflow Notification Area")
            if ($bar -eq [IntPtr]::Zero) { $bar = [MpTrayButton]::FindChild($overflow, "ToolbarWindow32", $null) }
            if ([MpTrayButton]::FindNamed($bar, "MP Mix Manager")) {
                $sourceX = [MpTrayButton]::FoundX
                $sourceY = [MpTrayButton]::FoundY
                if ([MpTrayButton]::Where($sourceX, $sourceY) -ne "NotifyIconOverflowWindow") {
                    if ($step.Tries -ge 12) { throw "icon is covered" }
                    return $false
                }
                $dest = New-Object MpTrayButton+RECT
                [MpTrayButton]::GetWindowRect($promoted, [ref]$dest) | Out-Null
                $destX = [int]($dest.L + 8)
                $destY = [int](($dest.T + $dest.B) / 2)
                if ([MpTrayButton]::Where($destX, $destY) -ne "Shell_TrayWnd") { throw "taskbar icon area is covered" }
                $down = $false
                try {
                    if (-not [MpTrayButton]::Place($sourceX, $sourceY)) { throw "could not reach the icon" }
                    if ([MpTrayButton]::Where($sourceX, $sourceY) -ne "NotifyIconOverflowWindow") { throw "icon is covered" }
                    [MpTrayButton]::mouse_event(2, 0, 0, 0, [UIntPtr]::Zero)
                    $down = $true
                    Start-Sleep -Milliseconds 150
                    if (-not [MpTrayButton]::Place($destX, $destY)) { throw "could not reach the taskbar" }
                    if ([MpTrayButton]::Where($destX, $destY) -ne "Shell_TrayWnd") { throw "taskbar icon area is covered" }
                    Start-Sleep -Milliseconds 150
                    [MpTrayButton]::mouse_event(4, 0, 0, 0, [UIntPtr]::Zero)
                    $down = $false
                    Start-Sleep -Milliseconds 400
                } finally {
                    if ($down) { [MpTrayButton]::mouse_event(4, 0, 0, 0, [UIntPtr]::Zero) }
                    [MpTrayButton]::Restore()
                }
                $step.Phase = "settle"
                return $false
            }
            if ($step.Tries -ge 12) { throw "icon is not in the overflow" }
            return $false
        }
        "settle" {
            throw "icon did not stay on the taskbar"
        }
    }
    return $false
}

function Invoke-MpTrayClick {
    param([int]$X, [int]$Y, [string]$ExpectedClass)
    if ([MpTrayButton]::Where($X, $Y) -ne $ExpectedClass) { return $false }
    if (-not [MpTrayButton]::Place($X, $Y)) {
        [MpTrayButton]::Restore()
        return $false
    }
    if ([MpTrayButton]::Where($X, $Y) -ne $ExpectedClass) {
        [MpTrayButton]::Restore()
        return $false
    }
    [MpTrayButton]::mouse_event(2, 0, 0, 0, [UIntPtr]::Zero)
    Start-Sleep -Milliseconds 40
    [MpTrayButton]::mouse_event(4, 0, 0, 0, [UIntPtr]::Zero)
    [MpTrayButton]::Restore()
    return $true
}

function Close-MpOverflowChevron {
    param([int]$X, [int]$Y)
    if ([MpTrayButton]::FindVisible("NotifyIconOverflowWindow") -eq [IntPtr]::Zero) { return }
    if ([MpTrayButton]::Where($X, $Y) -ne "Shell_TrayWnd") { return }
    Invoke-MpTrayClick -X $X -Y $Y -ExpectedClass "Shell_TrayWnd" | Out-Null
}

$notify = $null
$timer = $null
$script:promoteTimer = $null
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
    $script:promoteTimer = New-Object System.Windows.Forms.Timer
    $script:promoteTimer.Interval = 1000
    $script:promoteTimer.Add_Tick({
        $script:promoteTimer.Interval = 500
        try {
            if (Show-MpTrayButton) { $script:promoteTimer.Stop() }
        } catch {
            Write-MpTrayLog "promote $($_.Exception.Message)"
            try { Close-MpOverflowChevron -X $script:trayPromote.ChevronX -Y $script:trayPromote.ChevronY } catch { }
            try { [MpTrayButton]::Restore() } catch { }
            $script:promoteTimer.Stop()
        }
    })
    $script:promoteTimer.Start()
    Write-MpTrayLog "ready pid=$PID"
    [System.Windows.Forms.Application]::Run()
} catch {
    Write-MpTrayLog "failed pid=$PID $($_.Exception.Message)"
    exit 1
} finally {
    if ($script:promoteTimer) { $script:promoteTimer.Stop(); $script:promoteTimer.Dispose() }
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
