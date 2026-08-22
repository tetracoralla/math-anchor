import AppKit
import SwiftUI

struct CalculatorWindowConfigurator: NSViewRepresentable {
    let contentSize: CGSize

    final class Coordinator {
        var configuredWindow: ObjectIdentifier?
        var appliedContentSize: CGSize?
    }

    func makeCoordinator() -> Coordinator {
        Coordinator()
    }

    func makeNSView(context: Context) -> NSView {
        let view = NSView()
        configureWhenAttached(view, coordinator: context.coordinator)
        return view
    }

    func updateNSView(_ view: NSView, context: Context) {
        configureWhenAttached(view, coordinator: context.coordinator)
    }

    private func configureWhenAttached(_ view: NSView, coordinator: Coordinator) {
        let size = contentSize
        DispatchQueue.main.async {
            guard let window = view.window else { return }
            let windowID = ObjectIdentifier(window)
            if coordinator.configuredWindow != windowID {
                coordinator.configuredWindow = windowID
                coordinator.appliedContentSize = nil
                Self.configureChrome(of: window)
            }
            guard coordinator.appliedContentSize != size else { return }
            let shouldAnimate =
                coordinator.appliedContentSize != nil
                && !NSWorkspace.shared.accessibilityDisplayShouldReduceMotion
            coordinator.appliedContentSize = size
            Self.resize(window, to: size, animated: shouldAnimate)
        }
    }

    /// Window chrome is a property of the window, not of the SwiftUI content;
    /// re-asserting it on every keystroke-driven update only churns AppKit.
    private static func configureChrome(of window: NSWindow) {
        window.titleVisibility = .hidden
        window.titlebarAppearsTransparent = true
        window.styleMask.insert(.fullSizeContentView)
        window.styleMask.remove(.resizable)
        window.isMovableByWindowBackground = true
        window.backgroundColor = .clear
        window.isOpaque = false
        window.hasShadow = true
        window.titlebarSeparatorStyle = .none
        window.standardWindowButton(.zoomButton)?.isEnabled = false
        window.makeFirstResponder(nil)
    }

    private static func resize(_ window: NSWindow, to contentSize: CGSize, animated: Bool) {
        let targetContentRect = NSRect(origin: .zero, size: contentSize)
        let targetWindowSize = window.frameRect(forContentRect: targetContentRect).size
        var targetFrame = window.frame
        targetFrame.origin.y += targetFrame.height - targetWindowSize.height
        targetFrame.size = targetWindowSize
        if let visibleFrame = (window.screen ?? NSScreen.main)?.visibleFrame {
            // Keep a growing window on screen: near the right edge the history
            // drawer and the scientific face expand leftward instead of
            // pushing the calculator off screen.
            if targetFrame.maxX > visibleFrame.maxX {
                targetFrame.origin.x = visibleFrame.maxX - targetFrame.width
            }
            if targetFrame.minY < visibleFrame.minY {
                targetFrame.origin.y = visibleFrame.minY
            }
        }
        window.contentMinSize = contentSize
        window.contentMaxSize = contentSize

        // One controllable timeline shared with the SwiftUI content
        // animation, instead of AppKit's fixed-duration setFrame animation
        // running against an instantly relaid-out view tree.
        if animated {
            NSAnimationContext.runAnimationGroup { context in
                context.duration = CalculatorLayout.modeTransitionDuration
                window.animator().setFrame(targetFrame, display: true)
            }
        } else {
            window.setFrame(targetFrame, display: true)
        }
    }
}
