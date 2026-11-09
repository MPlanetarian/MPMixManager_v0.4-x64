import AppKit
import Darwin

/// Menu-bar icon for MP Mix Manager. Menu actions call mp_system_tray.py so
/// launch, focus, and close stay in one place. PySide6 is not used.

private let terminateNow: @convention(c) (Int32) -> Void = { _ in
    _exit(0)
}

final class MenuBarController: NSObject, NSApplicationDelegate {
    let root: String
    let iconPath: String
    let python: String
    let stay: Bool
    let lockFD: Int32
    var statusItem: NSStatusItem?
    var absentSince: Date?
    var pollInFlight = false

    init(root: String, iconPath: String, python: String, stay: Bool, lockFD: Int32) {
        self.root = root
        self.iconPath = iconPath
        self.python = python
        self.stay = stay
        self.lockFD = lockFD
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        let item = NSStatusBar.system.statusItem(withLength: NSStatusItem.squareLength)
        if let button = item.button {
            if let image = NSImage(contentsOfFile: iconPath) {
                image.size = NSSize(width: 18, height: 18)
                image.isTemplate = false
                button.image = image
                button.imageScaling = .scaleProportionallyDown
            } else {
                button.title = "MP"
            }
            button.toolTip = "MP Mix Manager"
            button.setAccessibilityLabel("MP Mix Manager")
        }
        let menu = NSMenu()
        let entries = [
            ("launch-gui", "Launch MP Gui"),
            ("launch-liquid", "Launch MP Liquid Player"),
            ("launch-manager", "Launch MP Mix Manager"),
        ]
        for (ident, title) in entries {
            let menuItem = NSMenuItem(title: title, action: #selector(performAction(_:)), keyEquivalent: "")
            menuItem.target = self
            menuItem.representedObject = ident
            menu.addItem(menuItem)
        }
        menu.addItem(.separator())
        let closeItem = NSMenuItem(
            title: "Close MP Mix Manager (Closes everything)",
            action: #selector(performAction(_:)),
            keyEquivalent: ""
        )
        closeItem.target = self
        closeItem.representedObject = "close-all"
        menu.addItem(closeItem)
        item.menu = menu
        item.isVisible = true
        statusItem = item
        let hasImage = item.button?.image != nil
        if !stay {
            Timer.scheduledTimer(withTimeInterval: 2.0, repeats: true) { [weak self] _ in
                self?.pollRoles()
            }
        }
        fputs("ready pid=\(getpid()) image=\(hasImage)\n", stderr)
        fflush(stderr)
    }

    @objc func performAction(_ sender: NSMenuItem) {
        let action = sender.representedObject as? String ?? ""
        guard !action.isEmpty else { return }
        DispatchQueue.global(qos: .userInitiated).async {
            _ = self.runPython(["--action", action])
            if action == "close-all" {
                DispatchQueue.main.async {
                    NSApp.terminate(nil)
                }
            }
        }
    }

    func pollRoles() {
        if stay || pollInFlight {
            return
        }
        pollInFlight = true
        DispatchQueue.global(qos: .utility).async {
            let roles = self.runPython(["--roles"])
            DispatchQueue.main.async {
                self.pollInFlight = false
                // A failed check keeps the icon. Only a successful empty
                // reply means none of the three apps is open.
                guard let roles else { return }
                let empty = roles.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
                if !empty {
                    self.absentSince = nil
                    return
                }
                let now = Date()
                if self.absentSince == nil {
                    self.absentSince = now
                    return
                }
                if let started = self.absentSince, now.timeIntervalSince(started) >= 8 {
                    NSApp.terminate(nil)
                }
            }
        }
    }

    func runPython(_ extra: [String]) -> String? {
        let script = (root as NSString).appendingPathComponent("scripts/mp_system_tray.py")
        guard FileManager.default.isExecutableFile(atPath: python) else { return nil }
        guard FileManager.default.isReadableFile(atPath: script) else { return nil }
        let task = Process()
        task.executableURL = URL(fileURLWithPath: python)
        task.arguments = [script] + extra
        task.currentDirectoryURL = URL(fileURLWithPath: root)
        var env = ProcessInfo.processInfo.environment
        let prefix = "/opt/homebrew/bin:/usr/local/bin"
        if let path = env["PATH"], !path.isEmpty {
            env["PATH"] = prefix + ":" + path
        } else {
            env["PATH"] = prefix + ":/usr/bin:/bin"
        }
        task.environment = env
        let output = Pipe()
        task.standardOutput = output
        task.standardError = FileHandle.nullDevice
        do {
            try task.run()
        } catch {
            return nil
        }
        task.waitUntilExit()
        if task.terminationStatus != 0 {
            return nil
        }
        let data = output.fileHandleForReading.readDataToEndOfFile()
        return String(data: data, encoding: .utf8) ?? ""
    }
}

private func argumentValue(_ arguments: [String], _ name: String) -> String? {
    guard let index = arguments.firstIndex(of: name), index + 1 < arguments.count else {
        return nil
    }
    return arguments[index + 1]
}

private func acquireLock(path: String) -> Int32 {
    let parent = (path as NSString).deletingLastPathComponent
    try? FileManager.default.createDirectory(atPath: parent, withIntermediateDirectories: true)
    let fd = Darwin.open(path, O_RDWR | O_CREAT, mode_t(0o644))
    if fd < 0 {
        return -1
    }
    if flock(fd, LOCK_EX | LOCK_NB) != 0 {
        Darwin.close(fd)
        return -1
    }
    let text = String(getpid()) + "\n"
    _ = ftruncate(fd, 0)
    text.withCString { pointer in
        _ = Darwin.pwrite(fd, pointer, strlen(pointer), 0)
    }
    return fd
}

let arguments = CommandLine.arguments
guard let root = argumentValue(arguments, "--root"), !root.isEmpty else {
    fputs("macos_menu_bar: --root is required\n", stderr)
    exit(2)
}
guard let lockPath = argumentValue(arguments, "--lock"), !lockPath.isEmpty else {
    fputs("macos_menu_bar: --lock is required\n", stderr)
    exit(2)
}
let iconPath = argumentValue(arguments, "--icon") ?? ""
let python = argumentValue(arguments, "--python") ?? "/usr/bin/python3"
let stay = arguments.contains("--stay")
let lockFD = acquireLock(path: lockPath)
if lockFD < 0 {
    exit(0)
}
signal(SIGTERM, terminateNow)
signal(SIGINT, terminateNow)

let controller = MenuBarController(
    root: root,
    iconPath: iconPath,
    python: python,
    stay: stay,
    lockFD: lockFD
)
let app = NSApplication.shared
app.setActivationPolicy(.accessory)
app.delegate = controller
app.run()
