import Foundation

struct EvaluationResult: Equatable, Sendable {
    let exact: String?
    let approximate: String?

    var continuationValue: String {
        exact ?? approximate ?? "0"
    }

    var displayValue: String {
        guard let exact else { return approximate ?? "0" }
        if exact.range(of: #"^-?\d+$"#, options: .regularExpression) != nil {
            return exact
        }
        return approximate ?? exact
    }

    var distinctExactValue: String? {
        guard let exact, approximate != nil, displayValue != exact else { return nil }
        return exact
    }
}
