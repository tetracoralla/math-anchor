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
                key("x²", accessibilityLabel: "Square", action: store.square)
                key("x³", accessibilityLabel: "Cube", action: store.cube)
                key("xʸ", accessibilityLabel: "Raise to a power") { store.append("^") }
                function("sqrt", title: "√x")
                key("π") { store.append("pi") }
                key("e") { store.append("e") }
            }
            GridRow {
                key("1/x", accessibilityLabel: "Reciprocal", action: store.reciprocal)
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
        let labels = [
            "sqrt": "Square root", "sin": "Sine", "cos": "Cosine", "tan": "Tangent",
            "asin": "Inverse sine", "acos": "Inverse cosine", "atan": "Inverse tangent",
            "ln": "Natural logarithm", "log": "Base-10 logarithm", "exp": "Exponential",
            "factorial": "Factorial", "abs": "Absolute value",
            "sinh": "Hyperbolic sine", "cosh": "Hyperbolic cosine", "tanh": "Hyperbolic tangent",
            "floor": "Round down to an integer", "ceil": "Round up to an integer",
        ]
        return key(title ?? name, accessibilityLabel: labels[name]) { store.applyFunction(name) }
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
