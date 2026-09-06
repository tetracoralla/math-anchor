import Foundation

package enum AngleUnit: String, Codable, CaseIterable, Identifiable, Sendable {
    case radians
    case degrees

    package var id: String { rawValue }
    package var symbol: String { self == .radians ? "RAD" : "DEG" }
    package var title: String { self == .radians ? "Radians" : "Degrees" }

    package static func applies(to expression: String) -> Bool {
        // A word boundary does not exist between a digit and a letter, so
        // legacy history text such as `2sin(30)` must be matched with a
        // letter-exclusion lookbehind instead.
        expression.range(of: #"(?<![A-Za-z])(a?sin|a?cos|a?tan)\("#, options: .regularExpression) != nil
    }
}
