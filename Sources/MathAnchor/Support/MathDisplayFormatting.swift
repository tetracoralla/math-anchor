import Foundation

enum MathDisplayFormatting {
    static func expression(_ value: String) -> String {
        value
            .replacingOccurrences(of: "**", with: "^")
            .replacingOccurrences(of: "*", with: "×")
            .replacingOccurrences(of: "/", with: "÷")
            .replacingOccurrences(of: "-", with: "−")
    }

}
