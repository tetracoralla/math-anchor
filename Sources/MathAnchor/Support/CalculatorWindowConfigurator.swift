import AppKit
import SwiftUI
import MathAnchorCore

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
        // `fullSizeContentView` makes AppKit's frame/content conversion report
        // the whole frame as content, while SwiftUI still lays this view out
        // below `contentLayoutRect`'s titlebar safe area.  Using
        // frameRect(forContentRect:) here therefore removed that inset on the
        // first mode switch: the 492 pt basic layout was forced into a 492 pt
        // frame instead of the 524 pt frame it needs, clipping the keypad's
        // bottom clearance. Preserve the live chrome inset explicitly so the
        // requested size always remains the usable SwiftUI layout area.
        let chromeHeight = max(0, window.frame.height - window.contentLayoutRect.height)
        let targetWindowSize = CGSize(
            width: contentSize.width,
            height: contentSize.height + chromeHeight
        )
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
        // The calculator is non-resizable. Frame limits avoid reinterpreting
        // the usable content size through full-size-titlebar semantics.
        window.minSize = targetWindowSize
        window.maxSize = targetWindowSize

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
