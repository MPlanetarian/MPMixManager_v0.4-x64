import Cocoa
import AVFoundation

// Borderless startup logo window for macOS. The loader script compiles this
// once with swiftc and reuses the binary. It is the macOS counterpart of the
// Windows borderless WPF window: no title bar, floating, and closed when the
// movie ends or the user presses a key or clicks.

final class BorderlessWindow: NSWindow {
    override var canBecomeKey: Bool { return true }
    override var canBecomeMain: Bool { return true }
}

final class PlayerView: NSView {
    override func makeBackingLayer() -> CALayer {
        let playerLayer = AVPlayerLayer()
        playerLayer.videoGravity = .resizeAspect
        playerLayer.backgroundColor = NSColor.black.cgColor
        return playerLayer
    }

    var playerLayer: AVPlayerLayer {
        return layer as! AVPlayerLayer
    }

    override init(frame frameRect: NSRect) {
        super.init(frame: frameRect)
        wantsLayer = true
    }

    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }

    override var acceptsFirstResponder: Bool { return true }

    override func keyDown(with event: NSEvent) {
        NSApp.terminate(nil)
    }

    override func mouseDown(with event: NSEvent) {
        NSApp.terminate(nil)
    }
}

final class AppDelegate: NSObject, NSApplicationDelegate {
    var window: BorderlessWindow?
    var player: AVPlayer?

    func applicationDidFinishLaunching(_ notification: Notification) {
        let args = CommandLine.arguments
        guard args.count > 1 else {
            NSApp.terminate(nil)
            return
        }

        let url = URL(fileURLWithPath: args[1])
        let asset = AVURLAsset(url: url)
        let item = AVPlayerItem(asset: asset)
        let avPlayer = AVPlayer(playerItem: item)
        player = avPlayer

        let screen = NSScreen.main?.frame ?? NSRect(x: 0, y: 0, width: 1440, height: 900)
        var width: CGFloat = 800
        var height: CGFloat = 450
        let tracks = asset.tracks(withMediaType: .video)
        if let track = tracks.first {
            let transformed = track.naturalSize.applying(track.preferredTransform)
            let rawW = abs(transformed.width)
            let rawH = abs(transformed.height)
            if rawW > 1 && rawH > 1 {
                let maxW = screen.width * 0.6
                let maxH = screen.height * 0.6
                var scale = min(maxW / rawW, maxH / rawH)
                if scale > 1 {
                    scale = 1
                }
                width = rawW * scale
                height = rawH * scale
            }
        }
        if width < 320 {
            width = 320
        }
        if height < 180 {
            height = 180
        }

        let origin = NSPoint(x: screen.midX - width / 2, y: screen.midY - height / 2)
        let win = BorderlessWindow(
            contentRect: NSRect(x: origin.x, y: origin.y, width: width, height: height),
            styleMask: [.borderless],
            backing: .buffered,
            defer: false
        )
        win.level = .floating
        win.backgroundColor = .black
        win.isOpaque = true
        win.hasShadow = false
        win.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]
        win.title = ""

        let view = PlayerView(frame: NSRect(x: 0, y: 0, width: width, height: height))
        view.playerLayer.player = avPlayer
        win.contentView = view
        window = win
        win.orderFrontRegardless()
        win.makeKeyAndOrderFront(nil)
        win.makeFirstResponder(view)
        NSApp.activate(ignoringOtherApps: true)
        avPlayer.play()

        NotificationCenter.default.addObserver(
            forName: .AVPlayerItemDidPlayToEndTime,
            object: item,
            queue: .main
        ) { _ in
            NSApp.terminate(nil)
        }
        NotificationCenter.default.addObserver(
            forName: .AVPlayerItemFailedToPlayToEndTime,
            object: item,
            queue: .main
        ) { _ in
            NSApp.terminate(nil)
        }
    }
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.setActivationPolicy(.accessory)
app.run()
