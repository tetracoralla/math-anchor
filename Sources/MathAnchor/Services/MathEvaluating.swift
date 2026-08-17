import Foundation

protocol MathEvaluating: Sendable {
    func evaluate(expression: String, precision: Int) async throws -> EvaluationResult
    func cancelPendingEvaluation()
}

extension MathEvaluating {
    func cancelPendingEvaluation() {}
}

enum MathRuntimeError: LocalizedError, Equatable {
    case runtimeNotInstalled
    case invalidResponse
    case cancelled
    case timedOut
    case operation(String)

    var errorDescription: String? {
        switch self {
        case .runtimeNotInstalled:
            "The local calculation runtime is not installed. Run script/bootstrap.sh."
        case .invalidResponse:
            "The calculation runtime returned an invalid response."
        case .cancelled:
            "The calculation was cancelled."
        case .timedOut:
            "The calculation took too long and was stopped."
        case let .operation(message):
            message
        }
    }
}
