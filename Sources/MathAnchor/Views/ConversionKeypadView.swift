import SwiftUI
import MathAnchorCore

struct ConversionKeypadView: View {
    let store: UnitConversionStore

    var body: some View {
        Grid(horizontalSpacing: CalculatorLayout.keySpacing, verticalSpacing: CalculatorLayout.keySpacing) {
            GridRow {
                key(
                    "",
                    systemImage: "delete.backward",
                    accessibilityLabel: "Delete",
                    tone: .action,
                    symbolSize: 23,
                    action: store.backspace
                )
                key("AC", tone: .action, textSize: 16, action: store.clear)
                key(
                    "",
                    systemImage: "arrow.left.arrow.right",
                    accessibilityLabel: "Swap units",
                    tone: .operation,
                    symbolSize: 19,
                    action: store.swapUnits
                )
            }
            GridRow { digit("7"); digit("8"); digit("9") }
            GridRow { digit("4"); digit("5"); digit("6") }
            GridRow { digit("1"); digit("2"); digit("3") }
            GridRow {
                key("±", tone: .action, textSize: 19, textYOffset: -1, action: store.toggleSign)
                digit("0")
                key(
                    ".",
                    accessibilityLabel: "Decimal point",
                    textSize: 23,
                    textYOffset: -3.5,
                    action: store.appendDecimal
                )
            }
        }
        .frame(width: 260)
    }

    private func digit(_ value: String) -> some View {
        key(value) { store.appendDigit(value) }
    }

    private func key(
        _ title: String,
        systemImage: String? = nil,
        accessibilityLabel: String? = nil,
        tone: CalculatorButtonTone = .digit,
        symbolSize: CGFloat? = nil,
        textSize: CGFloat? = nil,
        textYOffset: CGFloat = 0,
        action: @escaping () -> Void
    ) -> some View {
        CalculatorKeyButton(
            title: title,
            systemImage: systemImage,
            accessibilityLabel: accessibilityLabel,
            tone: tone,
            width: CalculatorLayout.conversionKeyWidth,
            symbolSize: symbolSize,
            textSize: textSize,
            textYOffset: textYOffset,
            action: action
        )
    }
}

extension ConversionKeypadView: Equatable {
    nonisolated static func == (lhs: ConversionKeypadView, rhs: ConversionKeypadView) -> Bool {
        lhs.store === rhs.store
    }
}
