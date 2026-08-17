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

    static func fromRuntime(code: String?) -> MathRuntimeError {
        switch code {
        case "E_INPUT", "E_SYNTAX", "E_AST_BLOCK":
            .operation("Check the expression and complete any open parentheses.")
        case "E_NAME":
            .operation("Check the spelling of function and symbol names.")
        case "E_DOMAIN":
            .operation("This calculation is undefined for the current input.")
        case "E_TIMEOUT":
            .timedOut
        case "E_MEMORY", "E_OUTPUT_LIMIT", "E_LIMIT":
            .operation("This calculation is too large to complete.")
        case "E_UNIT":
            .operation("Choose compatible units.")
        default:
            .operation("Calculation failed.")
        }
    }

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
