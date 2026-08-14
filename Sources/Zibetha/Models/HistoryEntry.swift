import Foundation

struct HistoryEntry: Codable, Identifiable, Equatable, Sendable {
    let id: UUID
    let expression: String
    let executionExpression: String?
    let exact: String?
    let result: String
    let createdAt: Date

    init(
        id: UUID = UUID(),
        expression: String,
        executionExpression: String? = nil,
        exact: String?,
        result: String,
        createdAt: Date = Date()
    ) {
        self.id = id
        self.expression = expression
        self.executionExpression = executionExpression
        self.exact = exact
        self.result = result
        self.createdAt = createdAt
    }
}
