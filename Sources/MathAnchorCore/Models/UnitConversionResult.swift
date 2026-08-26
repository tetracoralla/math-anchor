import Foundation

package struct UnitConversionResult: Equatable, Sendable {
    package let exact: String?
    package let approximate: String?
    package let runtimeUnit: String
    package let warnings: [String]

    package var displayValue: String {
        guard let exact else { return approximate ?? "0" }
        if exact.range(of: #"^-?\d+$"#, options: .regularExpression) != nil {
            return exact
        }
        return approximate ?? exact
    }

    package var distinctExactValue: String? {
        guard let exact, approximate != nil, displayValue != exact else { return nil }
        return exact
    }
}
