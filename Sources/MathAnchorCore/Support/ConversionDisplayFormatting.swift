import Foundation

package enum ConversionDisplayFormatting {
    package static func value(_ value: String) -> String {
        guard value != "—", value != "…" else { return value }
        let withoutTrailingZeros = trimTrailingZeros(value)
        guard withoutTrailingZeros.count > 10,
              let number = Double(withoutTrailingZeros),
              number.isFinite
        else { return withoutTrailingZeros }

        return String(
            format: "%.8g",
            locale: Locale(identifier: "en_US_POSIX"),
            number
        )
    }

    private static func trimTrailingZeros(_ value: String) -> String {
        guard value.contains("."), !value.lowercased().contains("e") else { return value }
        var result = value
        while result.last == "0" {
            result.removeLast()
        }
        if result.last == "." {
            result.removeLast()
        }
        return result.isEmpty || result == "-" ? "0" : result
    }
}
