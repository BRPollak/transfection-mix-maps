import AppKit
import Foundation

/// A small native host for the bundled local Streamlit server.
/// Build with Swift 5 language mode for macOS 14 on Apple Silicon.
final class LauncherDelegate: NSObject, NSApplicationDelegate, NSWindowDelegate {
    private var window: NSWindow!
    private var statusLabel: NSTextField!
    private var detailLabel: NSTextField!
    private var openButton: NSButton!
    private var openMenuItem: NSMenuItem!
    private var child: Process?
    private var outputPipe: Pipe?
    private var logHandle: FileHandle?
    private var serverURL: URL?
    private var pendingOutput = Data()
    private let outputQueue = DispatchQueue(label: "local.mixmaps.launcher.output")
    private var quitting = false

    private let supportURL: URL = FileManager.default
        .urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
        .appendingPathComponent("Transfection Mix Maps", isDirectory: true)

    private var logURL: URL { supportURL.appendingPathComponent("launcher.log") }

    func applicationDidFinishLaunching(_ notification: Notification) {
        makeMenu()
        makeWindow()
        NSApp.activate(ignoringOtherApps: true)
        do {
            try prepareLog()
            try launchServer()
        } catch {
            showFailure("The app could not start.", detail: error.localizedDescription)
        }
    }

    private func makeMenu() {
        let menuBar = NSMenu()
        let rootItem = NSMenuItem()
        menuBar.addItem(rootItem)
        let appMenu = NSMenu(title: "Transfection Mix Maps")
        appMenu.autoenablesItems = false
        openMenuItem = NSMenuItem(title: "Open in Browser", action: #selector(openBrowser), keyEquivalent: "o")
        openMenuItem.target = self
        openMenuItem.isEnabled = false
        appMenu.addItem(openMenuItem)
        appMenu.addItem(NSMenuItem.separator())
        let quitItem = NSMenuItem(title: "Quit Transfection Mix Maps", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        quitItem.target = NSApp
        appMenu.addItem(quitItem)
        rootItem.submenu = appMenu
        NSApp.mainMenu = menuBar
    }

    private func makeWindow() {
        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 540, height: 286),
                          styleMask: [.titled, .closable, .miniaturizable],
                          backing: .buffered, defer: false)
        window.title = "Transfection Mix Maps"
        window.isReleasedWhenClosed = false
        window.delegate = self
        window.center()

        let version = Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "1.0.0"
        let versionLabel = NSTextField(labelWithString: "TRANSFECTION MIX MAPS · VERSION \(version)")
        versionLabel.font = .systemFont(ofSize: 11, weight: .semibold)
        versionLabel.textColor = .secondaryLabelColor
        let appIcon = NSImageView()
        appIcon.image = NSApp.applicationIconImage
        appIcon.imageScaling = .scaleProportionallyUpOrDown
        appIcon.widthAnchor.constraint(equalToConstant: 36).isActive = true
        appIcon.heightAnchor.constraint(equalToConstant: 36).isActive = true
        let identity = NSStackView(views: [appIcon, versionLabel])
        identity.orientation = .horizontal
        identity.alignment = .centerY
        identity.spacing = 10

        statusLabel = NSTextField(wrappingLabelWithString: "Starting your local app…")
        statusLabel.font = .systemFont(ofSize: 22, weight: .semibold)
        detailLabel = NSTextField(wrappingLabelWithString: "Your browser will open as soon as the app is ready.")
        detailLabel.font = .systemFont(ofSize: 13)
        detailLabel.textColor = .secondaryLabelColor
        detailLabel.isSelectable = true

        openButton = NSButton(title: "Open in browser", target: self, action: #selector(openBrowser))
        openButton.bezelStyle = .rounded
        openButton.isEnabled = false
        let quitButton = NSButton(title: "Quit", target: NSApp, action: #selector(NSApplication.terminate(_:)))
        quitButton.bezelStyle = .rounded
        let buttons = NSStackView(views: [openButton, quitButton])
        buttons.orientation = .horizontal
        buttons.spacing = 10

        let spacer = NSView()
        spacer.setContentHuggingPriority(.defaultLow, for: .vertical)
        let stack = NSStackView(views: [identity, statusLabel, detailLabel, spacer, buttons])
        stack.orientation = .vertical
        stack.alignment = .leading
        stack.spacing = 14
        stack.translatesAutoresizingMaskIntoConstraints = false
        let content = window.contentView!
        content.addSubview(stack)
        NSLayoutConstraint.activate([
            stack.leadingAnchor.constraint(equalTo: content.leadingAnchor, constant: 24),
            stack.trailingAnchor.constraint(equalTo: content.trailingAnchor, constant: -24),
            stack.topAnchor.constraint(equalTo: content.topAnchor, constant: 24),
            stack.bottomAnchor.constraint(equalTo: content.bottomAnchor, constant: -24),
            statusLabel.widthAnchor.constraint(equalTo: stack.widthAnchor),
            detailLabel.widthAnchor.constraint(equalTo: stack.widthAnchor),
        ])
        window.makeKeyAndOrderFront(nil)
    }

    private func prepareLog() throws {
        let manager = FileManager.default
        try manager.createDirectory(at: supportURL, withIntermediateDirectories: true,
                                    attributes: [.posixPermissions: 0o700])
        try manager.setAttributes([.posixPermissions: 0o700], ofItemAtPath: supportURL.path)
        if !manager.fileExists(atPath: logURL.path) {
            guard manager.createFile(atPath: logURL.path, contents: nil,
                                     attributes: [.posixPermissions: 0o600]) else {
                throw launchError("Could not create the local launcher log at \(logURL.path).")
            }
        }
        try manager.setAttributes([.posixPermissions: 0o600], ofItemAtPath: logURL.path)
        let handle = try FileHandle(forWritingTo: logURL)
        try handle.seekToEnd()
        try handle.write(contentsOf: Data("\n--- Launch \(ISO8601DateFormatter().string(from: Date())) ---\n".utf8))
        logHandle = handle
    }

    private func launchServer() throws {
        guard let resources = Bundle.main.resourceURL else {
            throw launchError("The app bundle is incomplete. Copy the complete app from its disk image and try again.")
        }
        let runtime = resources.appendingPathComponent("runtime", isDirectory: true)
        let python = runtime.appendingPathComponent("bin/python3")
        let appDirectory = resources.appendingPathComponent("app", isDirectory: true)
        let script = appDirectory.appendingPathComponent("launch.py")
        let manager = FileManager.default
        guard manager.isExecutableFile(atPath: python.path), manager.fileExists(atPath: script.path) else {
            throw launchError("A bundled app file is missing. Copy the complete app from its disk image and try again.")
        }

        var environment = ProcessInfo.processInfo.environment
        // Use only bundled Python packages, regardless of the user's shell setup.
        environment.removeValue(forKey: "PYTHONPATH")
        environment.removeValue(forKey: "VIRTUAL_ENV")
        environment["PYTHONHOME"] = runtime.path
        environment["PYTHONNOUSERSITE"] = "1"
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        environment["PYTHONUNBUFFERED"] = "1"
        environment["MIXMAP_STATE_DIR"] = supportURL.appendingPathComponent("local_state", isDirectory: true).path
        environment["STREAMLIT_SERVER_FILE_WATCHER_TYPE"] = "none"
        environment["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
        environment["STREAMLIT_SERVER_RUN_ON_SAVE"] = "false"
        environment["STREAMLIT_SERVER_HEADLESS"] = "true"

        let process = Process()
        process.executableURL = python
        process.arguments = [script.path, "--no-browser"]
        process.currentDirectoryURL = appDirectory
        process.environment = environment
        process.standardInput = FileHandle.nullDevice
        let pipe = Pipe()
        process.standardOutput = pipe
        process.standardError = pipe
        outputPipe = pipe
        pipe.fileHandleForReading.readabilityHandler = { [weak self] handle in
            let data = handle.availableData
            guard !data.isEmpty else {
                handle.readabilityHandler = nil
                return
            }
            self?.outputQueue.async { [weak self] in self?.receiveOutput(data) }
        }
        process.terminationHandler = { [weak self] completed in
            DispatchQueue.main.async { [weak self] in
                self?.serverExited(status: completed.terminationStatus)
            }
        }
        child = process
        try process.run()
    }

    /// Runs only on outputQueue; complete lines can span multiple pipe reads.
    private func receiveOutput(_ data: Data) {
        try? logHandle?.write(contentsOf: data)
        pendingOutput.append(data)
        while let newline = pendingOutput.firstIndex(of: 10) {
            let line = String(decoding: pendingOutput[..<newline], as: UTF8.self)
            pendingOutput.removeSubrange(...newline)
            guard let marker = line.range(of: "ready: http://127.0.0.1:") else { continue }
            let candidate = String(line[marker.lowerBound...].dropFirst("ready: ".count))
                .trimmingCharacters(in: .whitespacesAndNewlines)
            guard let url = URL(string: candidate), url.scheme == "http",
                  url.host == "127.0.0.1", let port = url.port, (1...65535).contains(port) else { continue }
            DispatchQueue.main.async { [weak self] in self?.serverReady(at: url) }
        }
        // Keep a malformed/no-newline log message from growing memory indefinitely.
        if pendingOutput.count > 65536 { pendingOutput.removeAll(keepingCapacity: true) }
    }

    private func serverReady(at url: URL) {
        guard !quitting, child?.isRunning == true, serverURL == nil else { return }
        serverURL = url
        statusLabel.stringValue = "Your app is ready."
        detailLabel.stringValue = "Use the app in your browser. Keep this window open while you work; Quit stops the local server."
        openButton.isEnabled = true
        openMenuItem.isEnabled = true
        openBrowser()
    }

    @objc private func openBrowser() {
        guard let url = serverURL, !quitting else { return }
        if !NSWorkspace.shared.open(url) {
            detailLabel.stringValue = "Open this address in your browser:\n\(url.absoluteString)"
        }
    }

    private func serverExited(status: Int32) {
        serverURL = nil
        openButton.isEnabled = false
        openMenuItem.isEnabled = false
        if quitting {
            NSApp.reply(toApplicationShouldTerminate: true)
        } else {
            showFailure("The local app has stopped.",
                        detail: status == 0 ? "Quit and reopen the app to start it again."
                            : "Quit and reopen the app to try again. The local server exited with code \(status).")
        }
    }

    private func showFailure(_ title: String, detail: String) {
        statusLabel.stringValue = title
        detailLabel.stringValue = "\(detail)\n\nLauncher log:\n\(logURL.path)"
        outputQueue.async { [weak self] in
            try? self?.logHandle?.write(contentsOf: Data("Launcher: \(title) \(detail)\n".utf8))
        }
        window.setContentSize(NSSize(width: 540, height: 360))
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }

    private func launchError(_ message: String) -> NSError {
        NSError(domain: "TransfectionMixMaps.Launcher", code: 1,
                userInfo: [NSLocalizedDescriptionKey: message])
    }

    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        guard let process = child, process.isRunning else { return .terminateNow }
        if !quitting {
            quitting = true
            statusLabel.stringValue = "Stopping the local app…"
            detailLabel.stringValue = "The app will close after its local server has stopped."
            openButton.isEnabled = false
            openMenuItem.isEnabled = false
            // launch.py handles SIGTERM and waits for its Streamlit child to exit.
            process.terminate()
        }
        return .terminateLater
    }

    func applicationWillTerminate(_ notification: Notification) {
        outputPipe?.fileHandleForReading.readabilityHandler = nil
        outputQueue.sync {
            try? logHandle?.synchronize()
            try? logHandle?.close()
        }
    }

    func windowShouldClose(_ sender: NSWindow) -> Bool {
        NSApp.terminate(nil)
        return false
    }

    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        window.makeKeyAndOrderFront(nil)
        openBrowser()
        return true
    }
}

let application = NSApplication.shared
let delegate = LauncherDelegate()
application.delegate = delegate
application.setActivationPolicy(.regular)
application.run()
