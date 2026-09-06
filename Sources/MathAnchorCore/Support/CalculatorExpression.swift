import Foundation

/// The entered notation is authoritative. Completed values are atomic references
/// with a display spelling and an executable value, never reparsed display text.
package struct CalculatorExpression {
    package var source = ""
    package var angleUnit: AngleUnit = .radians
    private struct BoundValue {
        let display: String
        let execution: String
    }
    private var values: [String: BoundValue] = [:]
    private var nextValueID = 0

    package var visible: String { replacingValues(in: source, forExecution: false) }

    package var evaluation: String {
        replacingValues(
            in: ExpressionEditing.evaluationExpression(forVisible: source, angleUnit: angleUnit),
            forExecution: true
        )
    }

    package mutating func bind(visible: String, evaluation: String) -> String {
        let token = "storedValue\(nextValueID)v"
        nextValueID += 1
        values[token] = BoundValue(display: visible, execution: evaluation)
        return token
    }

    package mutating func removeLast() {
        // Editing the digits of a recalled value deliberately turns that one
        // operand into ordinary input; unrelated exact operands stay bound.
        if let token = values.keys.first(where: { source.hasSuffix($0) }),
           let value = values[token] {
            source = String(source.dropLast(token.count)) + value.display
        }
        if !source.isEmpty { source.removeLast() }
    }

    private func replacingValues(in text: String, forExecution: Bool) -> String {
        var result = text
        for token in values.keys.sorted() {
            guard let value = values[token] else { continue }
            result = result.replacingOccurrences(
                of: token,
                with: forExecution ? "(\(value.execution))" : value.display
            )
        }
        return result
    }
}
