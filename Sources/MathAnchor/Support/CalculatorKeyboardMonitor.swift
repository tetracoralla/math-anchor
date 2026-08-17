@preconcurrency import AppKit
import SwiftUI

@MainActor
final class CalculatorKeyboardMonitor {
    private var eventMonitor: Any?

    func start(store: CalculatorStore, conversionStore: UnitConversionStore) {
        guard eventMonitor == nil else { return }
        eventMonitor = NSEvent.addLocalMonitorForEvents(matching: .keyDown) { event in
            let modifiers = event.modifierFlags.intersection(.deviceIndependentFlagsMask)
            if modifiers.contains(.command) || modifiers.contains(.control) || modifiers.contains(.option) {
                return event
            }

            let focusedResponder = event.window?.firstResponder ?? NSApp.keyWindow?.firstResponder
            switch event.keyCode {
            case 53:
                if store.isModePopoverPresented {
                    store.isModePopoverPresented = false
                    return nil
                }
                if conversionStore.dismissActivePopover() {
                    return nil
                }
                if Self.shouldDeferToFocusedTextInput(focusedResponder) {
                    return event
                }
                if store.mode == .conversion {
                    conversionStore.clear()
                } else {
                    store.clear()
                }
                return nil
            default:
                break
            }

            if Self.shouldDeferToFocusedTextInput(focusedResponder) {
                return event
            }

            switch event.keyCode {
            case 36, 76:
                if store.mode == .conversion {
                    conversionStore.refreshNow()
                } else {
                    store.evaluate()
                }
                return nil
            case 51, 117:
                if store.mode == .conversion {
                    conversionStore.backspace()
                } else {
                    store.backspace()
                }
                return nil
            default:
                break
            }

            guard let characters = event.charactersIgnoringModifiers, characters.count == 1 else {
                return event
            }
            if store.mode == .conversion {
                switch characters {
                case "0"..."9":
                    conversionStore.appendDigit(characters)
                    return nil
                case ".":
                    conversionStore.appendDecimal()
                    return nil
                case "-":
                    conversionStore.toggleSign()
                    return nil
                case "=":
                    conversionStore.refreshNow()
                    return nil
                default:
                    return event
                }
            }
            switch characters {
            case "0"..."9", ".", "+", "-", "*", "/", "^", "(", ")":
                store.append(characters)
                return nil
            case "%":
                store.percent()
                return nil
            case "=":
                store.evaluate()
                return nil
            default:
                return event
            }
        }
    }

    func stop() {
        guard let eventMonitor else { return }
        NSEvent.removeMonitor(eventMonitor)
        self.eventMonitor = nil
    }

    static func shouldDeferToFocusedTextInput(_ responder: NSResponder?) -> Bool {
        if let textView = responder as? NSTextView {
            return textView.isEditable
        }
        if let textField = responder as? NSTextField {
            return textField.isEditable
        }
        return false
    }

}

private struct CalculatorKeyboardModifier: ViewModifier {
    let store: CalculatorStore
    let conversionStore: UnitConversionStore
    @State private var monitor = CalculatorKeyboardMonitor()

    func body(content: Content) -> some View {
        content
            .onAppear { monitor.start(store: store, conversionStore: conversionStore) }
            .onDisappear { monitor.stop() }
    }
}

extension View {
    func calculatorKeyboard(
        _ store: CalculatorStore,
        conversionStore: UnitConversionStore
    ) -> some View {
        modifier(CalculatorKeyboardModifier(store: store, conversionStore: conversionStore))
    }
}
