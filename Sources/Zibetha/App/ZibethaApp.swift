import AppKit
import SwiftUI

final class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.regular)
        NSApp.activate(ignoringOtherApps: true)
    }
}

@main
struct ZibethaApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate
    @StateObject private var store: CalculatorStore
    @StateObject private var conversionStore: UnitConversionStore

    init() {
        let runtime = MathRuntimeService()
        _store = StateObject(wrappedValue: CalculatorStore(runtime: runtime))
        _conversionStore = StateObject(
            wrappedValue: UnitConversionStore(
                runtime: runtime,
                currencyRuntime: runtime
            )
        )
    }

    var body: some Scene {
        WindowGroup("Calculator") {
            ContentView(store: store, conversionStore: conversionStore)
        }
        .windowStyle(.hiddenTitleBar)
        .defaultPosition(.center)
        .defaultSize(width: CalculatorLayout.basicWidth, height: CalculatorLayout.windowHeight)
        .commands {
            CalculatorCommands(store: store, conversionStore: conversionStore)
        }
    }
}
