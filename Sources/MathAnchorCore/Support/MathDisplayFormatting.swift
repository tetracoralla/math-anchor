import Foundation

package enum MathDisplayFormatting {
    package static func expression(_ value: String) -> String {
        value
            .replacingOccurrences(of: "**", with: "^")
            .replacingOccurrences(of: "*", with: "×")
            .replacingOccurrences(of: "/", with: "÷")
            .replacingOccurrences(of: "-", with: "−")
            .replacingOccurrences(of: "pi", with: "π")
    }

}
