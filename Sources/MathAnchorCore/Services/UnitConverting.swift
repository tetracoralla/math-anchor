import Foundation

package protocol UnitConverting: Sendable {
    func convert(
        value: String,
        fromUnit: String,
        toUnit: String,
        precision: Int
    ) async throws -> UnitConversionResult
    func cancelPendingConversion()
}

package extension UnitConverting {
    func cancelPendingConversion() {}
}
