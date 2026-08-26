import Foundation

package struct EvaluationResult: Equatable, Sendable {
    package let exact: String?
    package let approximate: String?

    package var continuationValue: String {
        exact ?? approximate ?? "0"
    }

    package var displayValue: String {
        guard let exact else { return approximate ?? "0" }
        if exact.range(of: #"^-?\d+$"#, options: .regularExpression) != nil {
            return exact
        }
        guard let approximate else { return exact }
        return Self.trimmedForDisplay(approximate)
    }

    package var distinctExactValue: String? {
        guard let exact, approximate != nil, displayValue != exact else { return nil }
        return exact
    }

    /// Meaningless trailing zeros do not belong on the calculator face; the
    /// full runtime strings stay available through copy and the exact-value
    /// affordance. Exponent forms are left untouched.
    package static func trimmedForDisplay(_ value: String) -> String {
        guard value.contains("."), !value.lowercased().contains("e") else { return value }
        var trimmed = value
        while trimmed.hasSuffix("0") {
            trimmed.removeLast()
        }
        if trimmed.hasSuffix(".") {
            trimmed.removeLast()
        }
        return trimmed
    }
}
