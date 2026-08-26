import Foundation

package protocol CurrencyConverting: Sendable {
    func convertCurrency(
        value: String,
        fromCurrency: String,
        toCurrency: String,
        precision: Int,
        forceRefresh: Bool
    ) async throws -> CurrencyConversionResult
    func cancelPendingCurrencyConversion()
}

package extension CurrencyConverting {
    func cancelPendingCurrencyConversion() {}
}
