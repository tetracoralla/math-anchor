import Foundation

package enum CurrencyRateState: String, Equatable, Sendable {
    case current
    case expired
}

package struct CurrencyRateMetadata: Equatable, Sendable {
    package let sourceName: String
    package let sourceShortName: String
    package let sourceURL: URL
    package let rateDate: String
    package let publishedAt: Date?
    package let checkedAt: Date
    package let expiresAt: Date
    package let nextRefreshAttemptAt: Date?
    package let state: CurrencyRateState
    package let isCached: Bool
    package let refreshFailed: Bool
    package let refreshDeferred: Bool

    package init(
        sourceName: String,
        sourceShortName: String,
        sourceURL: URL,
        rateDate: String,
        publishedAt: Date?,
        checkedAt: Date,
        expiresAt: Date,
        nextRefreshAttemptAt: Date? = nil,
        state: CurrencyRateState,
        isCached: Bool,
        refreshFailed: Bool,
        refreshDeferred: Bool = false
    ) {
        self.sourceName = sourceName
        self.sourceShortName = sourceShortName
        self.sourceURL = sourceURL
        self.rateDate = rateDate
        self.publishedAt = publishedAt
        self.checkedAt = checkedAt
        self.expiresAt = expiresAt
        self.nextRefreshAttemptAt = nextRefreshAttemptAt
        self.state = state
        self.isCached = isCached
        self.refreshFailed = refreshFailed
        self.refreshDeferred = refreshDeferred
    }

    package func isExpired(at date: Date = .now) -> Bool {
        state == .expired || date >= expiresAt
    }
}

package struct CurrencyConversionResult: Equatable, Sendable {
    package let approximate: String
    package let currency: String
    package let rate: CurrencyRateMetadata
    package let warnings: [String]

    package var displayValue: String {
        approximate
    }
}
