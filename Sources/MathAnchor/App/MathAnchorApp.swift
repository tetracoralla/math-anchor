import AppKit
import SwiftUI
import MathAnchorCore

final class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.regular)
        NSApp.activate(ignoringOtherApps: true)
    }
}

@main
struct MathAnchorApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate
    @StateObject private var store: CalculatorStore
    @StateObject private var conversionStore: UnitConversionStore
    @StateObject private var modeTransition: CalculatorModeTransition

    init() {
        let runtime = MathRuntimeService()
        _store = StateObject(wrappedValue: CalculatorStore(runtime: runtime))
        _conversionStore = StateObject(
            wrappedValue: UnitConversionStore(
                runtime: runtime,
                currencyRuntime: runtime
            )
        )
        _modeTransition = StateObject(wrappedValue: CalculatorModeTransition())
    }

    var body: some Scene {
        WindowGroup("Calculator") {
            ContentView(
                store: store,
                conversionStore: conversionStore,
                modeTransition: modeTransition
            )
        }
        .windowStyle(.hiddenTitleBar)
        .defaultPosition(.center)
        .defaultSize(width: CalculatorLayout.basicWidth, height: CalculatorLayout.windowHeight)
        .commands {
            CalculatorCommands(
                store: store,
                conversionStore: conversionStore,
                modeTransition: modeTransition
            )
        }
    }
}
