import SwiftUI

struct BasicKeypadView: View {
    let store: CalculatorStore

    var body: some View {
        Grid(horizontalSpacing: CalculatorLayout.keySpacing, verticalSpacing: CalculatorLayout.keySpacing) {
            GridRow {
                key(
                    "",
                    systemImage: "delete.backward",
                    accessibilityLabel: "Delete",
                    tone: .action,
                    symbolSize: 23,
                    symbolYOffset: -0.25,
                    action: store.backspace
                )
                key(
                    "AC",
                    tone: .action,
                    shortcut: .escape,
                    textSize: 16,
                    textYOffset: -0.25,
                    action: store.clear
                )
                key("%", tone: .action, shortcut: "%", textSize: 18, action: store.percent)
                operatorKey(systemImage: "divide", label: "Divide", shortcut: "/") {
                    store.append("/")
                }
            }
            GridRow {
                digit("7")
                digit("8")
                digit("9")
                operatorKey(systemImage: "multiply", label: "Multiply", shortcut: "*") {
                    store.append("*")
                }
            }
            GridRow {
                digit("4")
                digit("5")
                digit("6")
                operatorKey(systemImage: "minus", label: "Subtract", shortcut: "-") {
                    store.append("-")
                }
            }
            GridRow {
                digit("1")
                digit("2")
                digit("3")
                operatorKey(systemImage: "plus", label: "Add", shortcut: "+") {
                    store.append("+")
                }
            }
            GridRow {
                key("±", tone: .action, textSize: 19, textYOffset: -1, action: store.toggleSign)
                key("0", shortcut: "0") { store.append("0") }
                key(
                    ".",
                    accessibilityLabel: "Decimal point",
                    shortcut: ".",
                    textSize: 23,
                    textYOffset: -3.5
                ) {
                    store.append(".")
                }
                operatorKey(
                    systemImage: "equal",
                    label: "Equals",
                    shortcut: .return,
                    tone: .commit,
                    action: store.evaluate
                )
            }
        }
        .frame(width: 260)
    }

    private func digit(_ value: String) -> some View {
        key(value, shortcut: KeyEquivalent(Character(value))) { store.append(value) }
    }
    private func key(
        _ title: String,
        systemImage: String? = nil,
        accessibilityLabel: String? = nil,
        tone: CalculatorButtonTone = .digit,
        shortcut: KeyEquivalent? = nil,
        symbolSize: CGFloat? = nil,
        symbolYOffset: CGFloat = 0,
        textSize: CGFloat? = nil,
        textYOffset: CGFloat = 0,
        action: @escaping () -> Void
    ) -> some View {
        CalculatorKeyButton(
            title: title,
            systemImage: systemImage,
            accessibilityLabel: accessibilityLabel,
            tone: tone,
            shortcut: shortcut,
            width: CalculatorLayout.basicKeyWidth,
            symbolSize: symbolSize,
            symbolYOffset: symbolYOffset,
            textSize: textSize,
            textYOffset: textYOffset,
            action: action
        )
    }

    private func operatorKey(
        systemImage: String,
        label: String,
        shortcut: KeyEquivalent,
        tone: CalculatorButtonTone = .operation,
        action: @escaping () -> Void
    ) -> some View {
        key(
            "",
            systemImage: systemImage,
            accessibilityLabel: label,
            tone: tone,
            shortcut: shortcut,
            symbolSize: 22,
            action: action
        )
    }
}

extension BasicKeypadView: Equatable {
    nonisolated static func == (lhs: BasicKeypadView, rhs: BasicKeypadView) -> Bool {
        lhs.store === rhs.store
    }
}
