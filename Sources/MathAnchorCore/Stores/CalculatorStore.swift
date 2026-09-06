import Combine
import Foundation

@MainActor
package final class CalculatorStore: ObservableObject {
    @Published package var mode: CalculatorMode = .basic
    @Published package private(set) var angleUnit: AngleUnit = .radians
    @Published private var draft = CalculatorExpression()
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
    private var memoryEvaluation: String?
    private var lastExact: String?
    private var showingResult = false
    private var inputRevision = 0
    private var activeEvaluationID: UUID?
    private var evaluationTask: Task<Void, Never>?
    private var semanticUndo: [String: CalculatorExpression] = [:]
    private let maximumOperandDigits = 18

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

    package var expression: String { draft.visible }
    package var expressionForDisplay: String { MathDisplayFormatting.expression(expression) }
    package var isShowingResult: Bool { showingResult }
    package var canStoreMemory: Bool {
        !isEvaluating && errorMessage == nil
            && (draft.source.isEmpty || !endsWithOperatorOrOpeningParenthesis(draft.source))
    }

    package func selectMode(_ mode: CalculatorMode) {
        if self.mode != mode { invalidatePendingEvaluation() }
        self.mode = mode
        isModePopoverPresented = false
        if mode == .conversion { isHistoryPresented = false }
    }

    package func selectAngleUnit(_ unit: AngleUnit) {
        guard unit != angleUnit else { return }
        invalidatePendingEvaluation()
        angleUnit = unit
        draft.angleUnit = unit
    }

    package func replaceExpression(_ value: String) {
        invalidatePendingEvaluation()
        draft = CalculatorExpression()
        draft.angleUnit = angleUnit
        draft.source = value
        semanticUndo.removeAll(keepingCapacity: true)
        lastExact = nil
        updateEntryDisplay()
    }

    package func append(_ token: String) {
        guard !(showingResult && token == ")") else { return }
        if showingResult {
            if ["+", "-", "*", "/", "^"].contains(token) {
                prepareResultForEditing()
            } else {
                draft = CalculatorExpression()
                draft.angleUnit = angleUnit
            }
            semanticUndo.removeAll(keepingCapacity: true)
        }
        guard let edit = normalizedAppend(token) else { return }
        invalidatePendingEvaluation()
        draft.source = edit
        updateEntryDisplay()
    }

    package func appendFunction(_ name: String) { applyFunction(name) }

    package func applyFunction(_ name: String) {
        if draft.source.isEmpty || endsWithOperatorOrOpeningParenthesis(draft.source) {
            append("\(name)(")
            return
        }
        prepareResultForEditing()
        guard let split = ExpressionEditing.trailingOperand(in: draft.source),
              let edited = ExpressionEditing.replacingTrailingOperand(
                in: draft.source, with: "\(name)(\(split.operand))"
              ) else { return }
        transformExpression(edited)
    }

    package func square() { raiseCurrentExpression(to: 2) }
    package func cube() { raiseCurrentExpression(to: 3) }

    package func reciprocal() {
        if draft.source.isEmpty || endsWithOperatorOrOpeningParenthesis(draft.source) {
            append("1/(")
            return
        }
        prepareResultForEditing()
        guard let split = ExpressionEditing.trailingOperand(in: draft.source),
              let edited = ExpressionEditing.replacingTrailingOperand(
                in: draft.source, with: "1/(\(split.operand))"
              ) else { return }
        transformExpression(edited)
    }

    package func clear() { replaceExpression("") }

    package func backspace() {
        guard !draft.source.isEmpty else { return }
        if showingResult {
            // The first Delete opens the displayed value for digit editing.
            replaceExpression(ExpressionEditing.normalizedForRuntime(display))
            return
        }
        invalidatePendingEvaluation()
        if let previous = semanticUndo.removeValue(forKey: draft.source) {
            draft = previous
            draft.angleUnit = angleUnit
        } else {
            draft.removeLast()
        }
        updateEntryDisplay()
    }

    package func toggleSign() {
        guard !draft.source.isEmpty else { append("-"); return }
        prepareResultForEditing()
        guard let edited = ExpressionEditing.togglingSign(in: draft.source) else { return }
        transformExpression(edited)
    }

    package func percent() {
        guard !draft.source.isEmpty, !endsWithOperatorOrOpeningParenthesis(draft.source) else { return }
        prepareResultForEditing()
        guard !draft.source.hasSuffix("%") else { return }
        transformExpression(draft.source + "%")
    }

    package func evaluate() {
        guard !isEvaluating, !draft.source.isEmpty, !showingResult else { return }
        var submission = draft
        submission.source += String(repeating: ")", count: unmatchedOpeningParentheses(in: draft.source))
        let submittedExpression = submission.evaluation
        let submittedVisibleExpression = submission.visible
        let submittedRevision = inputRevision
        let evaluationID = UUID()
        activeEvaluationID = evaluationID
        isEvaluating = true
        errorMessage = nil
        evaluationTask = Task {
            guard !Task.isCancelled else { return }
            do {
                let result = try await runtime.evaluate(expression: submittedExpression, precision: 16)
                guard isCurrentEvaluation(evaluationID, revision: submittedRevision) else { return }
                finishEvaluation()
                lastExact = result.continuationValue
                display = result.displayValue
                distinctExactResult = result.distinctExactValue
                draft = submission
                showingResult = true
                history.insert(HistoryEntry(
                    expression: submittedVisibleExpression,
                    executionExpression: submittedExpression,
                    exact: result.exact,
                    result: result.displayValue,
                    angleUnit: AngleUnit.applies(to: submission.source) ? submission.angleUnit : nil
                ), at: 0)
                history = Array(history.prefix(100))
                historyStore.save(history)
            } catch {
                guard isCurrentEvaluation(evaluationID, revision: submittedRevision) else { return }
                finishEvaluation()
                errorMessage = error.localizedDescription
            }
        }
    }

    package func restore(_ entry: HistoryEntry) {
        if let unit = entry.angleUnit { selectAngleUnit(unit) }
        replaceExpression(entry.expression)
        display = entry.result
        lastExact = entry.exact ?? entry.result
        distinctExactResult = entry.exact == entry.result ? nil : entry.exact
        showingResult = true
    }

    package func clearHistory() {
        history = []
        historyStore.save(history)
    }

    package func copyResult() {
        clipboard.write(showingResult ? display : ExpressionEditing.normalizedForRuntime(expression))
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
        let isFresh = draft.source.isEmpty || showingResult
        if showingResult {
            draft = CalculatorExpression()
            draft.angleUnit = angleUnit
        }
        let token = draft.bind(visible: memory, evaluation: memoryEvaluation)
        let separator = !isFresh && endsValue(draft.source) ? "*" : ""
        invalidatePendingEvaluation()
        draft.source += isFresh ? token : "\(separator)(\(token))"
        updateEntryDisplay()
    }

    package func memoryAdd() { updateMemory(subtract: false) }
    package func memorySubtract() { updateMemory(subtract: true) }

    private func updateMemory(subtract: Bool) {
        guard canStoreMemory else { return }
        var completed = draft
        completed.source += String(repeating: ")", count: unmatchedOpeningParentheses(in: draft.source))
        let visible = showingResult ? display : (expression.isEmpty ? "0" : completed.visible)
        let evaluation = showingResult ? (lastExact ?? display) : (draft.source.isEmpty ? "0" : completed.evaluation)
        if let memory, let memoryEvaluation {
            let operation = subtract ? "-" : "+"
            self.memory = "\(memory)\(operation)(\(visible))"
            self.memoryEvaluation = "(\(memoryEvaluation))\(operation)(\(evaluation))"
        } else {
            memory = subtract ? "-(\(visible))" : visible
            memoryEvaluation = subtract ? "-(\(evaluation))" : evaluation
        }
    }

    private func prepareResultForEditing() {
        guard showingResult else { return }
        draft = CalculatorExpression()
        draft.angleUnit = angleUnit
        draft.source = draft.bind(visible: display, evaluation: lastExact ?? display)
        showingResult = false
        semanticUndo.removeAll(keepingCapacity: true)
    }

    private func raiseCurrentExpression(to exponent: Int) {
        guard !draft.source.isEmpty else { return }
        prepareResultForEditing()
        transformExpression("(\(draft.source))^\(exponent)")
    }

    private func transformExpression(_ edited: String) {
        let previous = draft
        invalidatePendingEvaluation()
        semanticUndo[edited] = previous
        draft.source = edited
        updateEntryDisplay()
    }

    private func updateEntryDisplay() {
        display = expression.isEmpty ? "0" : expressionForDisplay
        errorMessage = nil
        distinctExactResult = nil
        showingResult = false
    }

    private func finishEvaluation() {
        evaluationTask = nil
        activeEvaluationID = nil
        isEvaluating = false
    }

    private func invalidatePendingEvaluation() {
        evaluationTask?.cancel()
        runtime.cancelPendingEvaluation()
        inputRevision &+= 1
        finishEvaluation()
    }

    private func isCurrentEvaluation(_ id: UUID, revision: Int) -> Bool {
        activeEvaluationID == id && inputRevision == revision
    }

    private func normalizedAppend(_ token: String) -> String? {
        let source = draft.source
        if ["+", "-", "*", "/", "^"].contains(token) {
            if source.isEmpty { return token == "-" ? "-" : nil }
            if endsWithOperatorOrOpeningParenthesis(source) {
                if source.last == "(" { return token == "-" ? source + token : nil }
                return String(source.dropLast()) + token
            }
        }
        if token == "." {
            if currentNumberContainsDecimal(source) { return nil }
            if source.isEmpty || endsWithOperatorOrOpeningParenthesis(source) { return source + "0." }
            if endsNonNumericValue(source) { return source + "*0." }
        }
        if token == ")" {
            guard unmatchedOpeningParentheses(in: source) > 0,
                  !endsWithOperatorOrOpeningParenthesis(source) else { return nil }
        }
        if token.count == 1, token.first?.isNumber == true {
            if let replacement = replacingLoneLeadingZero(token) { return replacement }
            if trailingNumberDigitCount(in: source) >= maximumOperandDigits { return nil }
        }
        let startsValue = token.first?.isLetter == true || token.first == "("
        let digitFollowsValue = token.count == 1 && token.first?.isNumber == true && endsNonNumericValue(source)
        let separator = (startsValue && endsValue(source)) || digitFollowsValue ? "*" : ""
        return source + separator + token
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
    private func replacingLoneLeadingZero(_ digit: String) -> String? {
        guard let range = trailingNumberRange(in: draft.source) else { return nil }
        let number = String(draft.source[range])
        guard number == "0" || number == "-0" || number == "−0" else { return nil }
        return String(draft.source[..<range.lowerBound]) + digit
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
