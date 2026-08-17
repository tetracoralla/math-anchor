import Foundation

enum CurrencyRateState: String, Equatable, Sendable {
    case current
    case expired
}

struct CurrencyRateMetadata: Equatable, Sendable {
    let sourceName: String
    let sourceShortName: String
    let sourceURL: URL
    let rateDate: String
    let publishedAt: Date?
    let checkedAt: Date
    let expiresAt: Date
    let nextRefreshAttemptAt: Date?
    let state: CurrencyRateState
    let isCached: Bool
    let refreshFailed: Bool
    let refreshDeferred: Bool

    init(
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

    func isExpired(at date: Date = .now) -> Bool {
        state == .expired || date >= expiresAt
    }
}

struct CurrencyConversionResult: Equatable, Sendable {
    let approximate: String
    let currency: String
    let rate: CurrencyRateMetadata
    let warnings: [String]

    var displayValue: String {
        approximate
    }
}
