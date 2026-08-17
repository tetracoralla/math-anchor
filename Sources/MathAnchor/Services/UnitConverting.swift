import Foundation

protocol UnitConverting: Sendable {
    func convert(
        value: String,
        fromUnit: String,
        toUnit: String,
        precision: Int
    ) async throws -> UnitConversionResult
    func cancelPendingConversion()
}

extension UnitConverting {
    func cancelPendingConversion() {}
}
