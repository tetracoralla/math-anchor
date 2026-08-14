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
        DispatchQueue.main.async {
            guard let window = view.window else { return }
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

            let windowID = ObjectIdentifier(window)
            if coordinator.configuredWindow != windowID {
                coordinator.configuredWindow = windowID
                window.makeFirstResponder(nil)
            }

            guard coordinator.appliedContentSize != contentSize else { return }
            let shouldAnimate = coordinator.appliedContentSize != nil
            coordinator.appliedContentSize = contentSize

            let targetContentRect = NSRect(origin: .zero, size: contentSize)
            let targetWindowSize = window.frameRect(forContentRect: targetContentRect).size
            var targetFrame = window.frame
            targetFrame.origin.y += targetFrame.height - targetWindowSize.height
            targetFrame.size = targetWindowSize
            window.setFrame(targetFrame, display: true, animate: shouldAnimate)
            window.contentMinSize = contentSize
            window.contentMaxSize = contentSize
        }
    }
}
