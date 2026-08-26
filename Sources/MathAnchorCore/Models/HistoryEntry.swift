import Foundation

package struct HistoryEntry: Codable, Identifiable, Equatable, Sendable {
    package let id: UUID
    package let expression: String
    package let executionExpression: String?
    package let exact: String?
    package let result: String
    package let createdAt: Date

    package init(
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
