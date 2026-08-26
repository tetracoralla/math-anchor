import SwiftUI
import MathAnchorCore

struct CalculatorCommands: Commands {
    @ObservedObject var store: CalculatorStore
    @ObservedObject var conversionStore: UnitConversionStore
    let modeTransition: CalculatorModeTransition

    var body: some Commands {
        CommandGroup(replacing: .newItem) {}

        CommandMenu("Calculator") {
            Button("Calculate") {
                if store.mode == .conversion {
                    conversionStore.refreshNow()
                } else {
                    store.evaluate()
                }
            }
                .keyboardShortcut(.return, modifiers: [.command])
            Button("Copy Result") {
                if store.mode == .conversion {
                    conversionStore.copyResult()
                } else {
                    store.copyResult()
                }
            }
                .keyboardShortcut("c", modifiers: [.command])
            Button("Copy Exact Value") {
                if store.mode == .conversion {
                    conversionStore.copyExactResult()
                } else {
                    store.copyExactResult()
                }
            }
                .keyboardShortcut("c", modifiers: [.command, .option])
                .disabled(
                    store.mode == .conversion
                        ? conversionStore.distinctExactResult == nil
                        : store.distinctExactResult == nil
                )
            Divider()
            Button("Delete") {
                if store.mode == .conversion {
                    conversionStore.backspace()
                } else {
                    store.backspace()
                }
            }
                .keyboardShortcut(.delete, modifiers: [])
            Button("Clear") {
                if store.mode == .conversion {
                    conversionStore.clear()
                } else {
                    store.clear()
                }
            }
                .keyboardShortcut("k", modifiers: [.command])
        }

        CommandMenu("Mode") {
            Button("Basic") {
                modeTransition.select(
                    .basic,
                    calculatorStore: store,
                    conversionStore: conversionStore
                )
            }
                .keyboardShortcut("1", modifiers: [.command])
            Button("Scientific") {
                modeTransition.select(
                    .scientific,
                    calculatorStore: store,
                    conversionStore: conversionStore
                )
            }
                .keyboardShortcut("2", modifiers: [.command])
            Button("Convert") {
                modeTransition.select(
                    .conversion,
                    calculatorStore: store,
                    conversionStore: conversionStore
                )
            }
            .keyboardShortcut("3", modifiers: [.command])
            Divider()
            Button(store.isHistoryPresented ? "Hide History" : "Show History") {
                store.isHistoryPresented.toggle()
            }
            .keyboardShortcut("h", modifiers: [.command, .shift])
            .disabled(store.mode == .conversion)
        }
    }
}
