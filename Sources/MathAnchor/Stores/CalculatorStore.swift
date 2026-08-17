import Combine
import Foundation

@MainActor
final class CalculatorStore: ObservableObject {
    @Published var mode: CalculatorMode = .basic
    @Published var expression = ""
    @Published var display = "0"
    @Published var errorMessage: String?
    @Published var isEvaluating = false
    @Published var isHistoryPresented = false
    @Published var isModePopoverPresented = false
    @Published private(set) var history: [HistoryEntry]
    @Published private(set) var memory: String?
    @Published private(set) var distinctExactResult: String?

    private let runtime: any MathEvaluating
    private let historyStore: HistoryStore
    private let clipboard: any ClipboardWriting
    private var evaluationExpression = ""
    private var memoryEvaluation: String?
    private var lastExact: String?
    private var showingResult = false
    private var inputRevision = 0
    private var activeEvaluationID: UUID?
    private var semanticUndo: [String: ExpressionState] = [:]

    private struct ExpressionState {
        let visible: String
        let evaluation: String
    }

    init(
        runtime: any MathEvaluating = MathRuntimeService(),
        historyStore: HistoryStore = HistoryStore(),
        clipboard: (any ClipboardWriting)? = nil
    ) {
        self.runtime = runtime
        self.historyStore = historyStore
        self.clipboard = clipboard ?? SystemClipboard()
        history = historyStore.load()
    }

    var expressionForDisplay: String {
        MathDisplayFormatting.expression(expression)
    }

    var isShowingResult: Bool {
        showingResult
    }

    func selectMode(_ mode: CalculatorMode) {
        self.mode = mode
        isModePopoverPresented = false
        if mode == .conversion {
            isHistoryPresented = false
        }
    }

    func replaceExpression(_ value: String) {
        invalidatePendingEvaluation()
        expression = value
        evaluationExpression = ExpressionEditing.evaluationExpression(forVisible: value)
        semanticUndo.removeAll(keepingCapacity: true)
        display = value.isEmpty ? "0" : expressionForDisplay
        errorMessage = nil
        showingResult = false
        lastExact = nil
        distinctExactResult = nil
    }

    func append(_ token: String) {
        errorMessage = nil
        if showingResult {
            if ["+", "-", "*", "/", "^"].contains(token) {
                expression = display
                evaluationExpression = lastExact ?? display
            } else {
                expression = ""
                evaluationExpression = ""
            }
            semanticUndo.removeAll(keepingCapacity: true)
        }
        guard let edit = normalizedAppend(token) else { return }
        invalidatePendingEvaluation()
        showingResult = false
        expression = edit.visible
        evaluationExpression = edit.evaluation
        display = expressionForDisplay.isEmpty ? "0" : expressionForDisplay
        distinctExactResult = nil
    }

    func appendFunction(_ name: String) {
        if expression.isEmpty || endsWithOperatorOrOpeningParenthesis(expression) {
            append("\(name)(")
        } else {
            applyFunction(name)
        }
    }

    func applyFunction(_ name: String) {
        guard !expression.isEmpty else {
            append("\(name)(")
            return
        }
        if endsWithOperatorOrOpeningParenthesis(expression) {
            append("\(name)(")
            return
        }
        prepareResultForUnaryEditing()
        guard let visible = applyingToTrailingOperand(name, in: expression),
              let evaluation = applyingToTrailingOperand(name, in: evaluationExpression)
        else { return }
        transformExpressions(visible: visible, evaluation: evaluation)
    }

    func applyToCurrent(_ function: String) {
        guard !expression.isEmpty else {
            appendFunction(function)
            return
        }
        transformExpressions(
            visible: "\(function)(\(expression))",
            evaluation: "\(function)(\(evaluationExpression))"
        )
    }

    func square() {
        raiseCurrentExpression(to: 2)
    }

    func cube() {
        raiseCurrentExpression(to: 3)
    }

    func reciprocal() {
        guard !expression.isEmpty else { return }
        transformExpressions(
            visible: "1/(\(expression))",
            evaluation: "1/(\(evaluationExpression))"
        )
    }

    func clear() {
        invalidatePendingEvaluation()
        expression = ""
        evaluationExpression = ""
        semanticUndo.removeAll(keepingCapacity: false)
        display = "0"
        lastExact = nil
        distinctExactResult = nil
        errorMessage = nil
        showingResult = false
    }

    func backspace() {
        guard !expression.isEmpty else { return }
        if showingResult {
            clear()
            return
        }
        invalidatePendingEvaluation()
        if expression.hasSuffix("%") {
            expression.removeLast()
            evaluationExpression = ExpressionEditing.evaluationExpression(forVisible: expression)
            semanticUndo.removeValue(forKey: expression + "%")
        } else if let previous = semanticUndo.removeValue(forKey: expression) {
            expression = previous.visible
            evaluationExpression = previous.evaluation
        } else {
            expression.removeLast()
            if !evaluationExpression.isEmpty {
                evaluationExpression.removeLast()
            }
        }
        display = expression.isEmpty ? "0" : expressionForDisplay
        errorMessage = nil
    }

    func toggleSign() {
        guard !expression.isEmpty else {
            append("-")
            return
        }
        prepareResultForUnaryEditing()
        guard let visible = ExpressionEditing.togglingSign(in: expression),
              let evaluation = ExpressionEditing.togglingSign(in: evaluationExpression)
        else { return }
        transformExpressions(visible: visible, evaluation: evaluation)
    }

    func percent() {
        guard !expression.isEmpty else { return }
        prepareResultForUnaryEditing()
        guard let visibleSplit = ExpressionEditing.trailingOperand(in: expression),
              let evaluationSplit = ExpressionEditing.trailingOperand(in: evaluationExpression),
              !visibleSplit.operand.hasSuffix("%")
        else { return }

        let visibleReplacement = visibleSplit.operand + "%"
        let evaluationReplacement: String
        if let left = evaluationSplit.left,
           evaluationSplit.operatorToken == "+" || evaluationSplit.operatorToken == "-"
        {
            evaluationReplacement = "((\(left))*(\(evaluationSplit.operand))/100)"
        } else {
            evaluationReplacement = "(\(evaluationSplit.operand))/100"
        }
        guard let visible = ExpressionEditing.replacingTrailingOperand(
            in: expression,
            with: visibleReplacement
        ),
        let evaluation = ExpressionEditing.replacingTrailingOperand(
            in: evaluationExpression,
            with: evaluationReplacement
        ) else { return }
        transformExpressions(visible: visible, evaluation: evaluation)
    }

    func evaluate() {
        guard !isEvaluating, !expression.isEmpty else { return }
        let submittedExpression = evaluationExpression
        let submittedVisibleExpression = expression
        let submittedRevision = inputRevision
        let evaluationID = UUID()
        activeEvaluationID = evaluationID
        isEvaluating = true
        errorMessage = nil
        Task {
            do {
                let result = try await runtime.evaluate(expression: submittedExpression, precision: 16)
                guard isCurrentEvaluation(evaluationID, revision: submittedRevision) else { return }
                activeEvaluationID = nil
                isEvaluating = false
                lastExact = result.continuationValue
                display = result.displayValue
                distinctExactResult = result.distinctExactValue
                expression = submittedVisibleExpression
                evaluationExpression = submittedExpression
                showingResult = true
                let entry = HistoryEntry(
                    expression: submittedVisibleExpression,
                    executionExpression: submittedExpression,
                    exact: result.exact,
                    result: result.displayValue
                )
                history.insert(entry, at: 0)
                history = Array(history.prefix(100))
                historyStore.save(history)
            } catch {
                guard isCurrentEvaluation(evaluationID, revision: submittedRevision) else { return }
                activeEvaluationID = nil
                isEvaluating = false
                errorMessage = error.localizedDescription
            }
        }
    }

    func restore(_ entry: HistoryEntry) {
        invalidatePendingEvaluation()
        expression = entry.expression
        evaluationExpression = entry.executionExpression
            ?? ExpressionEditing.evaluationExpression(forVisible: entry.expression)
        display = entry.result
        lastExact = entry.exact ?? entry.result
        distinctExactResult = entry.exact == entry.result ? nil : entry.exact
        showingResult = true
        errorMessage = nil
    }

    func clearHistory() {
        history = []
        historyStore.save(history)
    }

    func copyResult() {
        clipboard.write(display)
    }

    func copyExactResult() {
        guard let distinctExactResult else { return }
        clipboard.write(distinctExactResult)
    }

    func memoryClear() {
        memory = nil
        memoryEvaluation = nil
    }

    func memoryRecall() {
        guard let memory, let memoryEvaluation else { return }
        let isFresh = expression.isEmpty || showingResult
        let separator = !isFresh && endsValue(expression) ? "*" : ""
        appendPaired(
            visible: isFresh ? memory : "\(separator)(\(memory))",
            evaluation: isFresh ? memoryEvaluation : "\(separator)(\(memoryEvaluation))"
        )
    }

    func memoryAdd() {
        let current = currentValue
        if let memory, let memoryEvaluation {
            self.memory = "\(memory)+(\(current.visible))"
            self.memoryEvaluation = "\(memoryEvaluation)+(\(current.evaluation))"
        } else {
            memory = current.visible
            memoryEvaluation = current.evaluation
        }
    }

    func memorySubtract() {
        let current = currentValue
        if let memory, let memoryEvaluation {
            self.memory = "\(memory)-(\(current.visible))"
            self.memoryEvaluation = "\(memoryEvaluation)-(\(current.evaluation))"
        } else {
            memory = "-(\(current.visible))"
            memoryEvaluation = "-(\(current.evaluation))"
        }
    }

    private var currentValue: ExpressionState {
        if showingResult {
            return ExpressionState(visible: display, evaluation: lastExact ?? display)
        }
        return ExpressionState(
            visible: expression.isEmpty ? "0" : expression,
            evaluation: evaluationExpression.isEmpty ? "0" : evaluationExpression
        )
    }

    private func prepareResultForUnaryEditing() {
        guard showingResult else { return }
        expression = display
        evaluationExpression = lastExact ?? display
        showingResult = false
    }

    private func raiseCurrentExpression(to exponent: Int) {
        guard !expression.isEmpty else { return }
        transformExpressions(
            visible: "(\(expression))^\(exponent)",
            evaluation: "(\(evaluationExpression))^\(exponent)"
        )
    }

    private func transformExpressions(visible: String, evaluation: String) {
        let previous = ExpressionState(visible: expression, evaluation: evaluationExpression)
        invalidatePendingEvaluation()
        semanticUndo[visible] = previous
        expression = visible
        evaluationExpression = evaluation
        display = expressionForDisplay
        distinctExactResult = nil
        showingResult = false
    }

    private func appendPaired(visible: String, evaluation: String) {
        errorMessage = nil
        if showingResult {
            expression = ""
            evaluationExpression = ""
            semanticUndo.removeAll(keepingCapacity: true)
        }
        invalidatePendingEvaluation()
        showingResult = false
        expression.append(visible)
        evaluationExpression.append(evaluation)
        display = expressionForDisplay.isEmpty ? "0" : expressionForDisplay
        distinctExactResult = nil
    }

    private func invalidatePendingEvaluation() {
        runtime.cancelPendingEvaluation()
        inputRevision &+= 1
        activeEvaluationID = nil
        isEvaluating = false
    }

    private func isCurrentEvaluation(_ id: UUID, revision: Int) -> Bool {
        activeEvaluationID == id && inputRevision == revision
    }

    private func normalizedAppend(_ token: String) -> ExpressionState? {
        let operators = ["+", "-", "*", "/", "^"]
        if operators.contains(token) {
            if expression.isEmpty {
                return token == "-" ? ExpressionState(visible: "-", evaluation: "-") : nil
            }
            if endsWithOperatorOrOpeningParenthesis(expression) {
                if expression.last == "(" {
                    return token == "-"
                        ? ExpressionState(
                            visible: expression + token,
                            evaluation: evaluationExpression + token
                        )
                        : nil
                } else {
                    let visible = String(expression.dropLast()) + token
                    let evaluation = String(evaluationExpression.dropLast()) + token
                    return ExpressionState(visible: visible, evaluation: evaluation)
                }
            }
        }

        if token == "." {
            if currentNumberContainsDecimal(expression) { return nil }
            if expression.isEmpty || endsWithOperatorOrOpeningParenthesis(expression) {
                return ExpressionState(
                    visible: expression + "0.",
                    evaluation: evaluationExpression + "0."
                )
            }
        }

        if token == ")" {
            guard unmatchedOpeningParentheses(in: expression) > 0,
                  !endsWithOperatorOrOpeningParenthesis(expression)
            else { return nil }
        }

        let tokenStartsNamedValue = token.first?.isLetter == true || token.first == "("
        let followsClosedValue = expression.last == ")" && (
            token.first?.isNumber == true || token.first == "."
        )
        let needsMultiplication = (tokenStartsNamedValue && endsValue(expression)) || followsClosedValue
        let separator = needsMultiplication ? "*" : ""
        return ExpressionState(
            visible: expression + separator + token,
            evaluation: evaluationExpression + separator + token
        )
    }

    private func applyingToTrailingOperand(_ function: String, in value: String) -> String? {
        guard let split = ExpressionEditing.trailingOperand(in: value) else { return nil }
        let replacement = "\(function)(\(split.operand))"
        return ExpressionEditing.replacingTrailingOperand(in: value, with: replacement)
    }

    private func endsWithOperatorOrOpeningParenthesis(_ value: String) -> Bool {
        guard let last = value.last else { return true }
        return "+-*/^(".contains(last)
    }

    private func currentNumberContainsDecimal(_ value: String) -> Bool {
        var current = ""
        for character in value.reversed() {
            if character.isNumber || character == "." || character == "e" || character == "E" {
                current.insert(character, at: current.startIndex)
            } else {
                break
            }
        }
        return current.contains(".")
    }

    private func unmatchedOpeningParentheses(in value: String) -> Int {
        value.reduce(into: 0) { depth, character in
            if character == "(" { depth += 1 }
            if character == ")" { depth = max(0, depth - 1) }
        }
    }

    private func endsValue(_ value: String) -> Bool {
        guard let last = value.last else { return false }
        return last.isNumber || last.isLetter || last == ")" || last == "%"
    }
}
