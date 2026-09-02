import Combine
import Foundation

@MainActor
package final class CalculatorStore: ObservableObject {
    @Published package var mode: CalculatorMode = .basic
    @Published package var expression = ""
    @Published package var display = "0"
    @Published package var errorMessage: String?
    @Published package var isEvaluating = false
    @Published package var isHistoryPresented = false
    @Published package var isModePopoverPresented = false
    @Published package private(set) var history: [HistoryEntry]
    @Published package private(set) var memory: String?
    @Published package private(set) var distinctExactResult: String?

    private let runtime: any MathEvaluating
    private let historyStore: HistoryStore
    private let clipboard: any ClipboardWriting
    private var evaluationExpression = ""
    private var memoryEvaluation: String?
    private var lastExact: String?
    private var lastSubmittedEvaluation = ""
    private var showingResult = false
    private var inputRevision = 0
    private var activeEvaluationID: UUID?
    private var evaluationTask: Task<Void, Never>?
    private var semanticUndo: [String: ExpressionState] = [:]

    private let maximumOperandDigits = 18

    private struct ExpressionState {
        let visible: String
        let evaluation: String
    }

    package init(
        runtime: any MathEvaluating = MathRuntimeService(),
        historyStore: HistoryStore = HistoryStore(),
        clipboard: (any ClipboardWriting)? = nil
    ) {
        self.runtime = runtime
        self.historyStore = historyStore
        self.clipboard = clipboard ?? SystemClipboard()
        history = historyStore.load()
    }

    package var expressionForDisplay: String {
        MathDisplayFormatting.expression(expression)
    }

    package var isShowingResult: Bool {
        showingResult
    }

    package func selectMode(_ mode: CalculatorMode) {
        if self.mode != mode {
            // A calculation belongs to the mode in which it was submitted.
            // Letting it survive a mode change can occupy the shared serial
            // app runtime and make the first conversion request time out.
            invalidatePendingEvaluation()
        }
        self.mode = mode
        isModePopoverPresented = false
        if mode == .conversion {
            isHistoryPresented = false
        }
    }

    package func replaceExpression(_ value: String) {
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

    package func append(_ token: String, evaluationToken: String? = nil) {
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
        guard let edit = normalizedAppend(token, evaluationToken: evaluationToken) else { return }
        invalidatePendingEvaluation()
        showingResult = false
        expression = edit.visible
        evaluationExpression = edit.evaluation
        display = expressionForDisplay.isEmpty ? "0" : expressionForDisplay
        distinctExactResult = nil
    }

    package func appendFunction(_ name: String) {
        if expression.isEmpty || endsWithOperatorOrOpeningParenthesis(expression) {
            appendFunctionCall(name)
        } else {
            applyFunction(name)
        }
    }

    package func applyFunction(_ name: String) {
        guard !expression.isEmpty else {
            appendFunctionCall(name)
            return
        }
        if endsWithOperatorOrOpeningParenthesis(expression) {
            appendFunctionCall(name)
            return
        }
        prepareResultForUnaryEditing()
        guard let visible = applyingToTrailingOperand(name, in: expression) else { return }
        // The executable string is re-derived from the edited visible string:
        // after a percent expansion the two strings are structurally
        // divergent, so trailing-operand surgery on the stale expansion would
        // splice the function onto the wrong operand.
        transformExpressions(
            visible: visible,
            evaluation: ExpressionEditing.evaluationExpression(forVisible: visible)
        )
    }

    package func square() {
        raiseCurrentExpression(to: 2)
    }

    package func cube() {
        raiseCurrentExpression(to: 3)
    }

    package func reciprocal() {
        guard !expression.isEmpty, !endsWithOperatorOrOpeningParenthesis(expression) else {
            appendFunction("1/")
            return
        }
        prepareResultForUnaryEditing()
        guard let visible = wrappingTrailingOperand(prefix: "1/", in: expression) else { return }
        transformExpressions(
            visible: visible,
            evaluation: ExpressionEditing.evaluationExpression(forVisible: visible)
        )
    }

    package func clear() {
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

    package func backspace() {
        guard !expression.isEmpty else { return }
        if showingResult {
            // Undo on the result returns to editing the value itself rather
            // than discarding the whole calculation.
            invalidatePendingEvaluation()
            let plain = ExpressionEditing.normalizedForRuntime(display)
            expression = plain
            evaluationExpression = plain
            lastExact = plain
            lastSubmittedEvaluation = ""
            showingResult = false
            distinctExactResult = nil
            display = expressionForDisplay.isEmpty ? "0" : expressionForDisplay
            errorMessage = nil
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
            // Visible and executable spellings are not always the same
            // (`log(` executes as `log10(`, and percent expands structurally).
            // Re-derive instead of deleting one hidden character and leaving
            // an invisible fragment behind after repeated backspace presses.
            evaluationExpression = ExpressionEditing.evaluationExpression(forVisible: expression)
        }
        display = expression.isEmpty ? "0" : expressionForDisplay
        errorMessage = nil
    }

    package func toggleSign() {
        guard !expression.isEmpty else {
            append("-")
            return
        }
        prepareResultForUnaryEditing()
        guard let visible = ExpressionEditing.togglingSign(in: expression) else { return }
        transformExpressions(
            visible: visible,
            evaluation: ExpressionEditing.evaluationExpression(forVisible: visible)
        )
    }

    package func percent() {
        guard !expression.isEmpty, !endsWithOperatorOrOpeningParenthesis(expression) else { return }
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
        } else if evaluationSplit.left != nil {
            evaluationReplacement = "(\(evaluationSplit.operand))/100"
        } else {
            // Without a left operand the percent divides the operand itself.
            // Appending (rather than wrapping) keeps the executable string's
            // open parentheses in lockstep with the visible suffix notation.
            evaluationReplacement = "\(evaluationSplit.operand)/100"
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

    package func evaluate() {
        guard !isEvaluating, !expression.isEmpty else { return }
        if showingResult && evaluationExpression == lastSubmittedEvaluation {
            // Re-pressing equals on the already-shown result is a repeat of
            // the completed submission, not a new calculation.
            return
        }
        // Familiar calculators close still-open groups at submission instead
        // of reporting a syntax error for work the machine can finish itself.
        let openGroups = unmatchedOpeningParentheses(in: evaluationExpression)
        let submittedExpression =
            evaluationExpression + String(repeating: ")", count: openGroups)
        let submittedVisibleExpression =
            expression + String(repeating: ")", count: unmatchedOpeningParentheses(in: expression))
        let submittedRevision = inputRevision
        let evaluationID = UUID()
        activeEvaluationID = evaluationID
        lastSubmittedEvaluation = submittedExpression
        isEvaluating = true
        errorMessage = nil
        evaluationTask = Task {
            guard !Task.isCancelled else { return }
            do {
                let result = try await runtime.evaluate(expression: submittedExpression, precision: 16)
                guard isCurrentEvaluation(evaluationID, revision: submittedRevision) else { return }
                evaluationTask = nil
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
                evaluationTask = nil
                activeEvaluationID = nil
                isEvaluating = false
                errorMessage = error.localizedDescription
            }
        }
    }

    package func restore(_ entry: HistoryEntry) {
        invalidatePendingEvaluation()
        expression = entry.expression
        evaluationExpression = entry.executionExpression
            ?? ExpressionEditing.evaluationExpression(forVisible: entry.expression)
        lastSubmittedEvaluation = evaluationExpression
        display = entry.result
        lastExact = entry.exact ?? entry.result
        distinctExactResult = entry.exact == entry.result ? nil : entry.exact
        showingResult = true
        errorMessage = nil
    }

    package func clearHistory() {
        history = []
        historyStore.save(history)
    }

    package func copyResult() {
        if showingResult {
            clipboard.write(display)
        } else {
            // Mid-entry the display carries presentation glyphs (×, ÷, −);
            // what lands on the pasteboard must stay plain ASCII.
            clipboard.write(ExpressionEditing.normalizedForRuntime(expression))
        }
    }

    package func copyExactResult() {
        guard let distinctExactResult else { return }
        clipboard.write(distinctExactResult)
    }

    package func memoryClear() {
        memory = nil
        memoryEvaluation = nil
    }

    package func memoryRecall() {
        guard let memory, let memoryEvaluation else { return }
        let isFresh = expression.isEmpty || showingResult
        let separator = !isFresh && endsValue(expression) ? "*" : ""
        appendPaired(
            visible: isFresh ? memory : "\(separator)(\(memory))",
            evaluation: isFresh ? memoryEvaluation : "\(separator)(\(memoryEvaluation))"
        )
    }

    package func memoryAdd() {
        let current = currentValue
        if let memory, let memoryEvaluation {
            self.memory = "\(memory)+(\(current.visible))"
            self.memoryEvaluation = "\(memoryEvaluation)+(\(current.evaluation))"
        } else {
            memory = current.visible
            memoryEvaluation = current.evaluation
        }
    }

    package func memorySubtract() {
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
        evaluationTask?.cancel()
        evaluationTask = nil
        runtime.cancelPendingEvaluation()
        inputRevision &+= 1
        activeEvaluationID = nil
        isEvaluating = false
    }

    private func isCurrentEvaluation(_ id: UUID, revision: Int) -> Bool {
        activeEvaluationID == id && inputRevision == revision
    }

    private func normalizedAppend(_ token: String, evaluationToken: String? = nil) -> ExpressionState? {
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
            if endsNonNumericValue(expression) {
                return ExpressionState(
                    visible: expression + "*0.",
                    evaluation: evaluationExpression + "*0."
                )
            }
        }

        if token == ")" {
            guard unmatchedOpeningParentheses(in: expression) > 0,
                  !endsWithOperatorOrOpeningParenthesis(expression),
                  unmatchedOpeningParentheses(in: evaluationExpression) > 0
            else { return nil }
        }

        if token.count == 1, token.first?.isNumber == true {
            if let replacement = replacingLoneLeadingZero(token) {
                return replacement
            }
            if trailingNumberDigitCount(in: expression) >= maximumOperandDigits {
                return nil
            }
        }

        let tokenStartsNamedValue = token.first?.isLetter == true || token.first == "("
        let digitFollowsNonNumericValue = token.count == 1
            && token.first?.isNumber == true
            && endsNonNumericValue(expression)
        let needsMultiplication = (tokenStartsNamedValue && endsValue(expression))
            || digitFollowsNonNumericValue
        let separator = needsMultiplication ? "*" : ""
        return ExpressionState(
            visible: expression + separator + token,
            evaluation: evaluationExpression + separator + (evaluationToken ?? token)
        )
    }

    /// Starts a named call with the visible spelling the user pressed and the
    /// core's executable spelling (the familiar `log` key runs as `log10`).
    private func appendFunctionCall(_ name: String) {
        append(
            "\(name)(",
            evaluationToken: ExpressionEditing.runtimeFunctionName(name) + "("
        )
    }

    private func applyingToTrailingOperand(_ function: String, in value: String) -> String? {
        guard let split = ExpressionEditing.trailingOperand(in: value) else { return nil }
        let replacement = "\(function)(\(split.operand))"
        return ExpressionEditing.replacingTrailingOperand(in: value, with: replacement)
    }

    private func wrappingTrailingOperand(prefix: String, in value: String) -> String? {
        guard let split = ExpressionEditing.trailingOperand(in: value) else { return nil }
        let replacement = "\(prefix)(\(split.operand))"
        return ExpressionEditing.replacingTrailingOperand(in: value, with: replacement)
    }

    /// Range of the number currently being entered, or nil when the entry
    /// does not end in digits (or ends inside an exponent, which stays
    /// untouched by familiar-calculator digit rules).
    private func trailingNumberRange(in value: String) -> Range<String.Index>? {
        let end = value.endIndex
        var start = end
        var sawDigit = false
        while start > value.startIndex {
            let candidate = value.index(before: start)
            let character = value[candidate]
            if character.isNumber {
                sawDigit = true
                start = candidate
            } else if character == "." && sawDigit {
                start = candidate
            } else {
                break
            }
        }
        guard sawDigit else { return nil }
        if start > value.startIndex {
            let before = value[value.index(before: start)]
            if before == "e" || before == "E" {
                let beforeBeforeIndex = value.index(before: start)
                if beforeBeforeIndex > value.startIndex {
                    let beforeBefore = value[value.index(before: beforeBeforeIndex)]
                    if beforeBefore.isNumber || beforeBefore == "." {
                        return nil
                    }
                } else {
                    return nil
                }
            }
        }
        return start..<end
    }

    private func trailingNumberDigitCount(in value: String) -> Int {
        guard let range = trailingNumberRange(in: value) else { return 0 }
        return value[range].filter(\.isNumber).count
    }

    /// A digit typed while the current operand is a lone zero replaces that
    /// zero, so `0` `0` `5` reads `5` instead of forming `005`, which the
    /// core would reject as a syntax error.
    private func replacingLoneLeadingZero(_ digit: String) -> ExpressionState? {
        guard let range = trailingNumberRange(in: expression) else { return nil }
        let number = String(expression[range])
        guard number == "0" || number == "-0" || number == "−0" else { return nil }
        guard let evaluationRange = trailingNumberRange(in: evaluationExpression),
              evaluationExpression.distance(
                  from: evaluationRange.lowerBound,
                  to: evaluationRange.upperBound
              ) == number.count
        else { return nil }

        // "-0" keeps its sign; only the zero itself is replaced.
        let replacementRange = number == "0"
            ? range
            : range.lowerBound..<expression.index(before: range.upperBound)
        let visible = expression.replacingCharacters(in: replacementRange, with: digit)
        let evaluationReplacementRange = number == "0"
            ? evaluationRange
            : evaluationRange.lowerBound..<evaluationExpression.index(before: evaluationRange.upperBound)
        let evaluation = evaluationExpression.replacingCharacters(
            in: evaluationReplacementRange,
            with: digit
        )
        return ExpressionState(visible: visible, evaluation: evaluation)
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

    private func endsNonNumericValue(_ value: String) -> Bool {
        guard let last = value.last else { return false }
        return last.isLetter || last == ")" || last == "%"
    }
}
