import SwiftUI
import MathAnchorCore

struct ScientificKeypadView: View {
    let store: CalculatorStore

    var body: some View {
        Grid(horizontalSpacing: CalculatorLayout.keySpacing, verticalSpacing: CalculatorLayout.keySpacing) {
            GridRow {
                key("(") { store.append("(") }
                key(")") { store.append(")") }
                MemoryRowView(store: store, keyWidth: CalculatorLayout.scientificKeyWidth)
                    .gridCellColumns(4)
            }
            GridRow {
                key("x²", action: store.square)
                key("x³", action: store.cube)
                key("xʸ") { store.append("^") }
                function("sqrt", title: "√x")
                key("π") { store.append("pi") }
                key("e") { store.append("e") }
            }
            GridRow {
                key("1/x", action: store.reciprocal)
                function("sin")
                function("cos")
                function("tan")
                function("ln")
                function("log")
            }
            GridRow {
                function("factorial", title: "n!")
                function("asin", title: "sin⁻¹")
                function("acos", title: "cos⁻¹")
                function("atan", title: "tan⁻¹")
                function("exp", title: "eˣ")
                function("abs", title: "|x|")
            }
            GridRow {
                function("sinh")
                function("cosh")
                function("tanh")
                function("floor", title: "floor")
                function("ceil", title: "ceil")
                key("i") { store.append("i") }
            }
        }
        .frame(width: 394)
    }

    private func function(_ name: String, title: String? = nil) -> some View {
        key(title ?? name) { store.applyFunction(name) }
    }

    private func key(
        _ title: String,
        accessibilityLabel: String? = nil,
        action: @escaping () -> Void
    ) -> some View {
        CalculatorKeyButton(
            title: title,
            accessibilityLabel: accessibilityLabel,
            tone: .scientific,
            width: CalculatorLayout.scientificKeyWidth,
            action: action
        )
    }
}

extension ScientificKeypadView: Equatable {
    nonisolated static func == (lhs: ScientificKeypadView, rhs: ScientificKeypadView) -> Bool {
        lhs.store === rhs.store
    }
}
