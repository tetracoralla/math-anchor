import AppKit
import Foundation

private struct SuccessfulRuntime: MathEvaluating {
    let result: EvaluationResult

    func evaluate(expression: String, precision: Int) async throws -> EvaluationResult {
        result
    }
}

private struct FailingRuntime: MathEvaluating {
    func evaluate(expression: String, precision: Int) async throws -> EvaluationResult {
        throw MathRuntimeError.operation("Invalid expression")
    }
}

private struct DelayedRuntime: MathEvaluating {
    func evaluate(expression: String, precision: Int) async throws -> EvaluationResult {
        if expression == "1+1" {
            try? await Task.sleep(nanoseconds: 120_000_000)
            return EvaluationResult(exact: "2", approximate: "2.000000000000000")
        }
        try? await Task.sleep(nanoseconds: 10_000_000)
        return EvaluationResult(exact: "4", approximate: "4.000000000000000")
    }
}

private struct SuccessfulUnitRuntime: UnitConverting {
    func convert(
        value: String,
        fromUnit: String,
        toUnit: String,
        precision: Int
    ) async throws -> UnitConversionResult {
        if fromUnit == "meter", toUnit == "foot" {
            return UnitConversionResult(
                exact: "1250/381",
                approximate: "3.28083989501",
                runtimeUnit: "ft",
                warnings: []
            )
        }
        return UnitConversionResult(
            exact: value,
            approximate: value,
            runtimeUnit: toUnit,
            warnings: []
        )
    }
}

private struct DelayedUnitRuntime: UnitConverting {
    func convert(
        value: String,
        fromUnit: String,
        toUnit: String,
        precision: Int
    ) async throws -> UnitConversionResult {
        if value == "12" {
            try? await Task.sleep(for: .milliseconds(120))
        } else {
            try? await Task.sleep(for: .milliseconds(10))
        }
        return UnitConversionResult(
            exact: value,
            approximate: value,
            runtimeUnit: toUnit,
            warnings: []
        )
    }
}

private final class RecordingCurrencyRuntime: CurrencyConverting, @unchecked Sendable {
    private let lock = NSLock()
    private var refreshFlags: [Bool] = []
    let state: CurrencyRateState
    let refreshFailed: Bool

    init(state: CurrencyRateState = .current, refreshFailed: Bool = false) {
        self.state = state
        self.refreshFailed = refreshFailed
    }

    func convertCurrency(
        value: String,
        fromCurrency: String,
        toCurrency: String,
        precision: Int,
        forceRefresh: Bool
    ) async throws -> CurrencyConversionResult {
        lock.withLock {
            refreshFlags.append(forceRefresh)
        }
        let published = Date(timeIntervalSince1970: 1_786_533_384)
        let checked = Date(timeIntervalSince1970: 1_786_610_100)
        return CurrencyConversionResult(
            approximate: toCurrency == "EUR" ? "0.85" : "7.2",
            currency: toCurrency,
            rate: CurrencyRateMetadata(
                sourceName: "European Central Bank",
                sourceShortName: "ECB",
                sourceURL: URL(string: "https://www.ecb.europa.eu/")!,
                rateDate: "2026-08-12",
                publishedAt: published,
                checkedAt: checked,
                expiresAt: checked.addingTimeInterval(86_400),
                state: state,
                isCached: true,
                refreshFailed: refreshFailed
            ),
            warnings: ["Reference rate"]
        )
    }

    var recordedRefreshFlags: [Bool] {
        lock.withLock { refreshFlags }
    }
}

private struct FailingCurrencyRuntime: CurrencyConverting {
    func convertCurrency(
        value: String,
        fromCurrency: String,
        toCurrency: String,
        precision: Int,
        forceRefresh: Bool
    ) async throws -> CurrencyConversionResult {
        throw MathRuntimeError.operation("Currency rates are unavailable.")
    }
}

private final class SucceedThenFailCurrencyRuntime: CurrencyConverting, @unchecked Sendable {
    private let lock = NSLock()
    private var callCount = 0

    func convertCurrency(
        value: String,
        fromCurrency: String,
        toCurrency: String,
        precision: Int,
        forceRefresh: Bool
    ) async throws -> CurrencyConversionResult {
        let call = lock.withLock {
            callCount += 1
            return callCount
        }
        if call > 1 {
            throw MathRuntimeError.operation("Currency rates are unavailable.")
        }
        return try await RecordingCurrencyRuntime().convertCurrency(
            value: value,
            fromCurrency: fromCurrency,
            toCurrency: toCurrency,
            precision: precision,
            forceRefresh: forceRefresh
        )
    }
}

@MainActor
private final class RecordingClipboard: ClipboardWriting {
    private(set) var value: String?

    func write(_ value: String) {
        self.value = value
    }
}

@main
struct CalculatorStoreChecks {
    @MainActor
    static func main() async {
        let suiteName = "MathAnchorChecks.\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: suiteName)!
        defer { defaults.removePersistentDomain(forName: suiteName) }
        let history = HistoryStore(defaults: defaults)
        let clipboard = RecordingClipboard()

        check(
            MathRuntimeError.fromRuntime(code: "E_SYNTAX").errorDescription
                == "Check the expression and complete any open parentheses.",
            "runtime parser diagnostics are translated into human-facing recovery copy"
        )
        check(
            MathRuntimeError.fromRuntime(code: "E_NAME").errorDescription
                == "Check the spelling of function and symbol names.",
            "unknown-name diagnostics point at spelling rather than parentheses"
        )
        check(
            MathRuntimeError.fromRuntime(code: "E_RUNTIME").errorDescription
                == "Calculation failed.",
            "runtime internals are not exposed in the calculator display"
        )
        check(
            MathRuntimeError.runtimeNotInstalled.errorDescription
                == "The calculation engine could not be started.",
            "startup failure copy stays free of developer instructions"
        )
        check(
            MathDisplayFormatting.expression("2*pi") == "2×π",
            "the pi constant renders as a glyph on the display"
        )
        check(
            EvaluationResult(exact: "103/20", approximate: "5.150000000000000").displayValue == "5.15",
            "result display drops meaningless trailing zeros"
        )

        let editableTextView = NSTextView()
        editableTextView.isEditable = true
        check(
            CalculatorKeyboardMonitor.shouldDeferToFocusedTextInput(editableTextView),
            "global calculator keyboard defers to an editable text field"
        )
        editableTextView.isEditable = false
        check(
            !CalculatorKeyboardMonitor.shouldDeferToFocusedTextInput(editableTextView),
            "global calculator keyboard may resume outside text editing"
        )

        let legacySuiteName = "\(suiteName).legacy"
        let legacyDefaults = UserDefaults(suiteName: legacySuiteName)!
        defer { legacyDefaults.removePersistentDomain(forName: legacySuiteName) }
        let legacyHistory = HistoryStore(defaults: legacyDefaults)
        legacyHistory.save([
            HistoryEntry(expression: "200+((200)*(10)/100)", exact: "220", result: "220"),
            HistoryEntry(expression: "2+-(3)", exact: "-1", result: "-1"),
            HistoryEntry(expression: "((0)+(3))", exact: "3", result: "3"),
        ])
        let migratedHistory = legacyHistory.load()
        check(
            migratedHistory.map(\.expression) == ["200+10%", "2-3", "3"],
            "legacy internal expressions migrate to readable history"
        )
        check(
            migratedHistory.first?.executionExpression == "200+((200)*(10)/100)",
            "legacy migration preserves the executable expression"
        )

        let inputStore = CalculatorStore(
            runtime: SuccessfulRuntime(result: EvaluationResult(exact: "0", approximate: "0")),
            historyStore: history,
            clipboard: clipboard
        )
        inputStore.append("1")
        inputStore.append("/")
        inputStore.append("3")
        check(inputStore.expression == "1/3", "input expression")
        check(inputStore.display == "1÷3", "human operator formatting")
        check(!inputStore.isShowingResult, "input state does not expose a secondary expression")
        inputStore.square()
        inputStore.applyFunction("sqrt")
        check(inputStore.expression == "(1/3)^sqrt(2)", "scientific transform")

        let guardedInputStore = CalculatorStore(
            runtime: SuccessfulRuntime(result: EvaluationResult(exact: "0", approximate: "0")),
            historyStore: history,
            clipboard: clipboard
        )
        guardedInputStore.append("1")
        guardedInputStore.append(".")
        guardedInputStore.append("2")
        guardedInputStore.append(".")
        check(guardedInputStore.expression == "1.2", "repeated decimal is ignored")
        guardedInputStore.append("+")
        guardedInputStore.append("*")
        check(guardedInputStore.expression == "1.2*", "a new operator replaces the pending operator")
        guardedInputStore.append("3")
        guardedInputStore.applyFunction("sin")
        check(guardedInputStore.expression == "1.2*sin(3)", "scientific function applies to the current operand")
        guardedInputStore.clear()
        guardedInputStore.append("(")
        guardedInputStore.append("+")
        check(guardedInputStore.expression == "(", "binary operator after opening parenthesis is ignored")
        guardedInputStore.append("2")
        guardedInputStore.append("+")
        guardedInputStore.applyFunction("sin")
        check(guardedInputStore.expression == "(2+sin(", "function begins the pending operand")

        let resultStore = CalculatorStore(
            runtime: SuccessfulRuntime(
                result: EvaluationResult(exact: "sqrt(2)", approximate: "1.414213562373095")
            ),
            historyStore: history,
            clipboard: clipboard
        )
        resultStore.appendFunction("sqrt")
        resultStore.append("2")
        resultStore.append(")")
        resultStore.evaluate()
        await waitForEvaluation(resultStore)
        check(resultStore.display == "1.414213562373095", "approximate display")
        check(resultStore.isShowingResult, "successful evaluation exposes expression and result")
        check(resultStore.distinctExactResult == "sqrt(2)", "distinct exact result remains available")
        check(resultStore.history.first?.exact == "sqrt(2)", "exact history value")
        resultStore.copyExactResult()
        check(clipboard.value == "sqrt(2)", "copy exact result")
        resultStore.copyResult()
        check(clipboard.value == "1.414213562373095", "copy result")
        resultStore.append("+")
        check(resultStore.expression == "1.414213562373095+", "continuation stays human-readable")
        check(!resultStore.isShowingResult, "continuation returns to single-line input state")
        check(resultStore.distinctExactResult == nil, "editing clears the prior exact-result affordance")
        resultStore.memoryAdd()
        check(resultStore.memory != nil, "memory add")

        let undoResultStore = CalculatorStore(
            runtime: SuccessfulRuntime(result: EvaluationResult(exact: "220", approximate: "220")),
            historyStore: history,
            clipboard: clipboard
        )
        undoResultStore.replaceExpression("200+20")
        undoResultStore.evaluate()
        await waitForEvaluation(undoResultStore)
        undoResultStore.backspace()
        check(undoResultStore.expression == "220", "undo on a result edits the value instead of clearing")
        check(!undoResultStore.isShowingResult, "undo on a result leaves result state")
        undoResultStore.backspace()
        check(undoResultStore.expression == "22", "further undo trims the edited value")

        let operandStore = CalculatorStore(
            runtime: SuccessfulRuntime(result: EvaluationResult(exact: "0", approximate: "0")),
            historyStore: history,
            clipboard: clipboard
        )
        operandStore.replaceExpression("200+10")
        operandStore.percent()
        check(operandStore.expression == "200+10%", "percent keeps the entered expression visible")
        operandStore.replaceExpression("2+3")
        operandStore.toggleSign()
        check(operandStore.expression == "2-3", "sign change stays human-readable")
        operandStore.toggleSign()
        check(operandStore.expression == "2+3", "sign change toggles back")
        operandStore.replaceExpression("2+3")
        operandStore.square()
        check(operandStore.expression == "(2+3)^2", "square applies to the whole current expression")
        operandStore.replaceExpression("2+3")
        operandStore.cube()
        check(operandStore.expression == "(2+3)^3", "cube matches square scope")
        operandStore.replaceExpression("2+3")
        operandStore.reciprocal()
        check(operandStore.expression == "2+1/(3)", "reciprocal matches the trailing-operand unary scope")
        operandStore.replaceExpression("2+3")
        operandStore.applyFunction("factorial")
        check(operandStore.expression == "2+factorial(3)", "factorial matches the trailing-operand unary scope")

        // Entry-machine regressions: each check pins a fix whose silent
        // revert would otherwise leave the suite green.
        let entryStore = CalculatorStore(
            runtime: SuccessfulRuntime(result: EvaluationResult(exact: "0", approximate: "0")),
            historyStore: history,
            clipboard: clipboard
        )
        entryStore.append("0")
        entryStore.append("0")
        check(entryStore.expression == "0", "a second digit replaces a lone leading zero")
        entryStore.append("5")
        check(entryStore.expression == "5", "digits after a lone zero do not form 005")
        entryStore.append("+")
        entryStore.append("0")
        entryStore.append("5")
        check(entryStore.expression == "5+5", "a lone zero operand is replaced mid-expression")
        entryStore.clear()
        for _ in 0..<19 {
            entryStore.append("1")
        }
        check(entryStore.expression.count == 18, "operand digit entry stops at the familiar limit")
        entryStore.clear()
        entryStore.append(")")
        check(entryStore.expression.isEmpty, "a closing parenthesis without an opening one is ignored")
        entryStore.appendFunction("sin")
        entryStore.percent()
        check(entryStore.expression == "sin(", "percent after an operator or open function is a no-op")
        entryStore.clear()
        entryStore.append("(")
        entryStore.append("2")
        entryStore.append("+")
        entryStore.append("3")
        entryStore.percent()
        entryStore.append(")")
        check(entryStore.expression == "(2+3%)", "percent keeps suffix notation inside a group")
        entryStore.clear()
        entryStore.append("2")
        entryStore.append("*")
        entryStore.append("3")
        entryStore.copyResult()
        check(clipboard.value == "2*3", "mid-entry copy stays plain ASCII")

        let memoryStore = CalculatorStore(
            runtime: SuccessfulRuntime(result: EvaluationResult(exact: "2", approximate: "2.000000000000000")),
            historyStore: history,
            clipboard: clipboard
        )
        memoryStore.append("2")
        memoryStore.evaluate()
        await waitForEvaluation(memoryStore)
        memoryStore.append("3")
        memoryStore.memoryAdd()
        check(memoryStore.memory == "3", "first memory add stores the current input without an internal zero")
        memoryStore.clear()
        memoryStore.memoryRecall()
        check(memoryStore.expression == "3", "memory recall stays human-readable")
        memoryStore.clear()
        memoryStore.append("4")
        memoryStore.memoryRecall()
        check(memoryStore.expression == "4*(3)", "memory recall inserts explicit multiplication after a value")
        memoryStore.clear()
        memoryStore.append("2")
        memoryStore.append("+")
        memoryStore.memoryRecall()
        check(memoryStore.expression == "2+(3)", "memory recall fills a pending operand")

        let staleStore = CalculatorStore(runtime: DelayedRuntime(), historyStore: history, clipboard: clipboard)
        staleStore.replaceExpression("1+1")
        staleStore.evaluate()
        staleStore.replaceExpression("2+2")
        staleStore.evaluate()
        await waitForEvaluation(staleStore)
        check(staleStore.display == "4", "new evaluation wins")
        // The abandoned 1+1 evaluation lands later; shared CI runners add
        // tens of milliseconds of async scheduling, so the window for the
        // stale result to arrive and be rejected stays generous and bounded.
        try? await Task.sleep(for: .milliseconds(400))
        check(staleStore.expression == "2+2", "stale result does not restore old expression")
        check(staleStore.display == "4", "stale result does not overwrite new result")

        let staleClearStore = CalculatorStore(runtime: DelayedRuntime(), historyStore: history, clipboard: clipboard)
        staleClearStore.replaceExpression("1+1")
        staleClearStore.evaluate()
        staleClearStore.clear()
        staleClearStore.append("9")
        // Clear already invalidated the evaluation, so completion is not
        // observable; wait out the delayed runtime's full window instead.
        try? await Task.sleep(for: .milliseconds(400))
        check(staleClearStore.expression == "9", "clear invalidates pending evaluation")
        check(staleClearStore.display == "9", "pending result does not overwrite input after clear")

        let failureStore = CalculatorStore(runtime: FailingRuntime(), historyStore: history, clipboard: clipboard)
        let historyCountBeforeFailure = failureStore.history.count
        failureStore.append("1")
        failureStore.append("/")
        failureStore.append("0")
        failureStore.evaluate()
        await waitForEvaluation(failureStore)
        check(failureStore.expression == "1/0", "failure preserves input")
        check(failureStore.display == "1÷0", "failure does not show a stale result")
        check(failureStore.history.count == historyCountBeforeFailure, "failure adds no history")
        check(failureStore.errorMessage == "Invalid expression", "failure is visible")

        let conversionStore = UnitConversionStore(
            runtime: SuccessfulUnitRuntime(),
            clipboard: clipboard
        )
        conversionStore.activate()
        await waitForConversion(conversionStore)
        check(conversionStore.input == "1", "conversion starts from one source unit")
        check(conversionStore.output == "3.28083989501", "conversion uses the supplied unit runtime")
        check(conversionStore.resultForDisplay == "3.2808399", "conversion display stays optically compact")
        check(conversionStore.sourceUnit.symbol == "m", "conversion starts with meters")
        check(conversionStore.targetUnit.symbol == "ft", "conversion starts with feet")
        check(conversionStore.distinctExactResult == "1250/381", "conversion preserves distinct exact output")
        conversionStore.copyResult()
        check(clipboard.value == "3.28083989501", "conversion result copies independently")
        conversionStore.copyExactResult()
        check(clipboard.value == "1250/381", "conversion exact result remains optionally copyable")
        conversionStore.swapUnits()
        await waitForConversion(conversionStore)
        check(conversionStore.sourceUnit.symbol == "ft", "swap moves the target unit to the source")
        check(conversionStore.targetUnit.symbol == "m", "swap moves the source unit to the target")
        check(conversionStore.input == "3.28083989501", "swap preserves the full converted value internally")
        check(conversionStore.inputForDisplay == "3.2808399", "swap presents the compact converted value")
        conversionStore.backspace()
        check(conversionStore.input == "3.280839", "editing continues from the value the user can see")
        check(
            ConversionDisplayFormatting.value("33.8000000000") == "33.8",
            "conversion display removes meaningless trailing zeros"
        )

        let celsius = HumanUnitCatalog.all.first { $0.id == "celsius" }!
        conversionStore.selectSource(celsius)
        await waitForConversion(conversionStore)
        check(conversionStore.targetUnit.id == "fahrenheit", "changing category selects a compatible target")
        check(
            conversionStore.targetChoices.allSatisfy { $0.category == .temperature },
            "target picker exposes only compatible units"
        )

        let retentionStore = UnitConversionStore(runtime: DelayedUnitRuntime())
        retentionStore.clear()
        await waitForConversion(retentionStore)
        retentionStore.appendDigit("2")
        try? await Task.sleep(for: .milliseconds(30))
        check(retentionStore.isConverting, "a value edit keeps a conversion in flight")
        check(retentionStore.output == "0", "the previous result stays visible while a value edit converts")
        check(!retentionStore.isAwaitingFirstResult, "a retained result is not presented as a first result")
        await waitForConversion(retentionStore)
        check(retentionStore.output == "2", "the replaced result lands")

        let slowRetentionStore = UnitConversionStore(runtime: DelayedUnitRuntime())
        slowRetentionStore.activate()
        await waitForConversion(slowRetentionStore)
        check(slowRetentionStore.output == "1", "slow-retention baseline result lands")
        slowRetentionStore.appendDigit("2")
        try? await Task.sleep(for: .milliseconds(200))
        check(
            slowRetentionStore.isShowingDelayedProgress,
            "a slow replacement stops presenting the retained result as current"
        )
        check(
            slowRetentionStore.resultForDisplay == "…",
            "a slow replacement exposes progress instead of pairing old output with new input"
        )
        await waitForConversion(slowRetentionStore)
        check(slowRetentionStore.output == "12", "slow replacement result lands")
        check(
            !slowRetentionStore.isShowingDelayedProgress,
            "replacement completion clears delayed progress"
        )

        let staleConversionStore = UnitConversionStore(runtime: DelayedUnitRuntime())
        staleConversionStore.clear()
        staleConversionStore.appendDigit("1")
        staleConversionStore.appendDigit("2")
        staleConversionStore.backspace()
        staleConversionStore.appendDigit("3")
        await waitForConversion(staleConversionStore)
        // Generous bounded window for the abandoned conversions to land
        // and be rejected on a loaded shared runner.
        try? await Task.sleep(for: .milliseconds(400))
        check(staleConversionStore.input == "13", "conversion keeps numeric keypad editing deterministic")
        check(staleConversionStore.output == "13", "stale conversion cannot overwrite the newest input")

        let currencyRuntime = RecordingCurrencyRuntime()
        let currencyStore = UnitConversionStore(
            runtime: SuccessfulUnitRuntime(),
            currencyRuntime: currencyRuntime,
            clipboard: clipboard
        )
        currencyStore.selectSource(HumanUnitCatalog.usDollar)
        await waitForConversion(currencyStore)
        check(currencyStore.isCurrencyConversion, "currency selection uses the existing conversion flow")
        check(currencyStore.targetUnit == HumanUnitCatalog.euro, "currency selection chooses a compatible target")
        check(currencyStore.output == "0.85", "currency result comes from the provider runtime")
        check(currencyStore.rateMetadata?.sourceShortName == "ECB", "currency exposes the provider source")
        check(currencyStore.rateMetadata?.rateDate == "2026-08-12", "currency exposes the rate date")
        check(currencyStore.rateMetadata?.state == .current, "currency exposes current rate state")
        check(
            currencyStore.targetChoices.count == 30
                && currencyStore.targetChoices.allSatisfy(\.isCurrency),
            "currency target picker contains only the current ECB currency catalog"
        )
        currencyStore.refreshRates()
        await waitForConversion(currencyStore)
        check(currencyRuntime.recordedRefreshFlags.last == true, "manual refresh bypasses a current cache")
        currencyStore.appendDigit("2")
        try? await Task.sleep(for: .milliseconds(30))
        check(
            currencyStore.rateMetadata != nil && currencyStore.output == "0.85",
            "value-only currency edits keep the previous result and rate footer stable"
        )
        await waitForConversion(currencyStore)
        failureStore.selectMode(.conversion)
        currencyStore.setPopover(.rateDetails, presented: true)
        check(currencyStore.activePopover == .rateDetails, "conversion owns one active popover")
        let modeTransition = CalculatorModeTransition(popoverSettleDelay: .milliseconds(20))
        modeTransition.select(
            .basic,
            calculatorStore: failureStore,
            conversionStore: currencyStore
        )
        check(currencyStore.activePopover == nil, "mode transition dismisses the conversion popover")
        check(failureStore.mode == .conversion, "mode transition retains the popover anchor while dismissal settles")
        await waitUntil { failureStore.mode == .basic }
        check(failureStore.mode == .basic, "mode transition completes after popover dismissal")

        failureStore.selectMode(.conversion)
        currencyStore.setPopover(.rateDetails, presented: true)
        modeTransition.toggleModeMenu(
            calculatorStore: failureStore,
            conversionStore: currencyStore
        )
        check(!failureStore.isModePopoverPresented, "mode menu waits for the previous popover to settle")
        await waitUntil { failureStore.isModePopoverPresented }
        check(failureStore.isModePopoverPresented, "mode menu opens after the previous popover settles")

        failureStore.isModePopoverPresented = false
        currencyStore.setPopover(.rateDetails, presented: true)
        currencyStore.setPopover(.rateDetails, presented: false)
        modeTransition.select(
            .basic,
            calculatorStore: failureStore,
            conversionStore: currencyStore
        )
        check(
            failureStore.mode == .conversion,
            "mode transition recognizes an AppKit-initiated popover dismissal"
        )
        await waitUntil { failureStore.mode == .basic }
        check(
            failureStore.mode == .basic,
            "mode transition waits after an AppKit-initiated popover dismissal"
        )

        let expiredCurrencyStore = UnitConversionStore(
            runtime: SuccessfulUnitRuntime(),
            currencyRuntime: RecordingCurrencyRuntime(state: .expired, refreshFailed: true)
        )
        expiredCurrencyStore.selectSource(HumanUnitCatalog.usDollar)
        await waitForConversion(expiredCurrencyStore)
        check(expiredCurrencyStore.output == "0.85", "expired cached rates remain usable")
        check(expiredCurrencyStore.rateMetadata?.state == .expired, "expired cache stays visibly expired")
        check(
            expiredCurrencyStore.rateMessage == "Refresh failed; using cached rates.",
            "failed refresh has a human recovery message"
        )

        let unavailableCurrencyStore = UnitConversionStore(
            runtime: SuccessfulUnitRuntime(),
            currencyRuntime: FailingCurrencyRuntime()
        )
        unavailableCurrencyStore.selectSource(HumanUnitCatalog.usDollar)
        await waitForConversion(unavailableCurrencyStore)
        check(unavailableCurrencyStore.output == "—", "unavailable rates do not invent a result")
        check(unavailableCurrencyStore.rateMetadata == nil, "unavailable rates expose no stale metadata")
        check(
            unavailableCurrencyStore.errorMessage == "Rates unavailable",
            "unavailable rates keep a compact human state"
        )

        let successThenFailureStore = UnitConversionStore(
            runtime: SuccessfulUnitRuntime(),
            currencyRuntime: SucceedThenFailCurrencyRuntime()
        )
        successThenFailureStore.selectSource(HumanUnitCatalog.usDollar)
        await waitForConversion(successThenFailureStore)
        check(successThenFailureStore.rateMetadata != nil, "successful currency request exposes current metadata")
        successThenFailureStore.refreshRates()
        await waitForConversion(successThenFailureStore)
        check(successThenFailureStore.output == "—", "failed refresh does not preserve an old result")
        check(successThenFailureStore.rateMetadata == nil, "failed refresh does not preserve old CURRENT metadata")
        check(successThenFailureStore.errorMessage == "Rates unavailable", "failed refresh becomes unavailable")

        let liveRuntime = MathRuntimeService()
        let liveFirst = try? await liveRuntime.evaluate(expression: "6*7", precision: 16)
        check(liveFirst?.exact == "42", "live runtime first result")
        let liveConversion = try? await liveRuntime.convert(
            value: "1000",
            fromUnit: "meter",
            toUnit: "kilometer",
            precision: 12
        )
        check(liveConversion?.displayValue == "1", "live warm runtime exposes the existing unit core")

        let livePercentStore = CalculatorStore(runtime: liveRuntime, historyStore: history, clipboard: clipboard)
        livePercentStore.replaceExpression("200+10")
        livePercentStore.percent()
        livePercentStore.evaluate()
        await waitForEvaluation(livePercentStore)
        check(livePercentStore.display == "220", "additive percent evaluates with Mac calculator semantics")
        check(livePercentStore.expression == "200+10%", "result state preserves the entered percent expression")
        check(livePercentStore.history.first?.expression == "200+10%", "history stores the visible percent expression")
        check(
            livePercentStore.history.first?.executionExpression == "200+((200)*(10)/100)",
            "history separately preserves the executable percent expression"
        )

        let liveSignStore = CalculatorStore(runtime: liveRuntime, historyStore: history, clipboard: clipboard)
        liveSignStore.replaceExpression("2+3")
        liveSignStore.toggleSign()
        liveSignStore.evaluate()
        await waitForEvaluation(liveSignStore)
        check(liveSignStore.display == "-1", "sign change evaluates only the current operand")
        check(liveSignStore.history.first?.expression == "2-3", "history stores the readable sign change")

        let liveParenPercentStore = CalculatorStore(runtime: liveRuntime, historyStore: history, clipboard: clipboard)
        liveParenPercentStore.append("(")
        liveParenPercentStore.append("5")
        liveParenPercentStore.append("+")
        liveParenPercentStore.append("3")
        liveParenPercentStore.percent()
        liveParenPercentStore.append(")")
        liveParenPercentStore.evaluate()
        await waitForEvaluation(liveParenPercentStore)
        check(liveParenPercentStore.display == "5.15", "percent inside a group keeps familiar additive semantics")
        check(
            liveParenPercentStore.history.first?.executionExpression == "(5+(((5)*(3)/100)))",
            "percent inside a group stores a balanced executable expression"
        )

        // Unary edits after a percent must stay faithful to the visible
        // notation: the executable string is re-derived from the edited
        // visible expression, never spliced onto the stale percent expansion.
        let unaryPercentStore = CalculatorStore(
            runtime: SuccessfulRuntime(result: EvaluationResult(exact: "0", approximate: "0")),
            historyStore: history,
            clipboard: clipboard
        )
        unaryPercentStore.replaceExpression("50")
        unaryPercentStore.percent()
        unaryPercentStore.applyFunction("sin")
        check(
            unaryPercentStore.expression == "sin(50%)",
            "function after percent keeps the visible percent notation"
        )
        unaryPercentStore.evaluate()
        await waitForEvaluation(unaryPercentStore)
        check(
            unaryPercentStore.history.first?.executionExpression == "sin((50)/100)",
            "function after percent stores a faithful executable expression"
        )
        unaryPercentStore.clear()
        unaryPercentStore.replaceExpression("50")
        unaryPercentStore.percent()
        unaryPercentStore.reciprocal()
        check(
            unaryPercentStore.expression == "1/(50%)",
            "reciprocal after percent wraps the percent operand"
        )
        unaryPercentStore.evaluate()
        await waitForEvaluation(unaryPercentStore)
        check(
            unaryPercentStore.history.first?.executionExpression == "1/((50)/100)",
            "reciprocal after percent stores a faithful executable expression"
        )
        unaryPercentStore.clear()
        unaryPercentStore.replaceExpression("200+10")
        unaryPercentStore.percent()
        unaryPercentStore.applyFunction("sin")
        check(
            unaryPercentStore.expression == "200+sin(10%)",
            "function after an additive percent wraps only the percent operand"
        )
        unaryPercentStore.evaluate()
        await waitForEvaluation(unaryPercentStore)
        check(
            unaryPercentStore.history.first?.executionExpression == "200+sin((10)/100)",
            "function after an additive percent keeps the expansion on the correct operand"
        )
        unaryPercentStore.clear()
        unaryPercentStore.replaceExpression("200+10")
        unaryPercentStore.percent()
        unaryPercentStore.toggleSign()
        check(
            unaryPercentStore.expression == "200-10%",
            "sign change after percent stays human-readable"
        )
        unaryPercentStore.evaluate()
        await waitForEvaluation(unaryPercentStore)
        check(
            unaryPercentStore.history.first?.executionExpression == "200-((200)*(10)/100)",
            "sign change after percent keeps the additive expansion on the flipped operator"
        )

        let liveUnaryPercentStore = CalculatorStore(runtime: liveRuntime, historyStore: history, clipboard: clipboard)
        liveUnaryPercentStore.replaceExpression("50")
        liveUnaryPercentStore.percent()
        liveUnaryPercentStore.applyFunction("sin")
        liveUnaryPercentStore.evaluate()
        await waitForEvaluation(liveUnaryPercentStore)
        check(
            liveUnaryPercentStore.display == "0.479425538604203",
            "function after percent evaluates the displayed operand"
        )
        liveUnaryPercentStore.clear()
        liveUnaryPercentStore.replaceExpression("50")
        liveUnaryPercentStore.percent()
        liveUnaryPercentStore.reciprocal()
        liveUnaryPercentStore.evaluate()
        await waitForEvaluation(liveUnaryPercentStore)
        check(
            liveUnaryPercentStore.display == "2",
            "reciprocal after percent evaluates the displayed operand"
        )
        liveUnaryPercentStore.clear()
        liveUnaryPercentStore.replaceExpression("200*10")
        liveUnaryPercentStore.percent()
        liveUnaryPercentStore.evaluate()
        await waitForEvaluation(liveUnaryPercentStore)
        check(liveUnaryPercentStore.display == "20", "multiplicative percent scales the operand")
        check(
            liveUnaryPercentStore.history.first?.executionExpression == "200*(10)/100",
            "multiplicative percent stores the operand-scaled executable expansion"
        )
        liveUnaryPercentStore.clear()
        liveUnaryPercentStore.replaceExpression("200+10")
        liveUnaryPercentStore.percent()
        liveUnaryPercentStore.append("+")
        liveUnaryPercentStore.append("5")
        liveUnaryPercentStore.percent()
        liveUnaryPercentStore.evaluate()
        await waitForEvaluation(liveUnaryPercentStore)
        check(liveUnaryPercentStore.display == "231", "chained percent compounds on the accumulated value")

        let liveLogStore = CalculatorStore(runtime: liveRuntime, historyStore: history, clipboard: clipboard)
        liveLogStore.appendFunction("log")
        liveLogStore.append("1")
        liveLogStore.append("0")
        liveLogStore.append("0")
        liveLogStore.evaluate()
        await waitForEvaluation(liveLogStore)
        check(liveLogStore.display == "2", "the log key computes the familiar base-10 logarithm")
        check(
            liveLogStore.history.first?.executionExpression == "log10(100)",
            "the log key submits the explicit base-10 executable name"
        )
        liveLogStore.clear()
        liveLogStore.appendFunction("log")
        liveLogStore.append("1")
        liveLogStore.append("0")
        liveLogStore.append("0")
        liveLogStore.backspace()
        check(
            liveLogStore.expression == "log(10",
            "backspace edits the still-open visible log argument"
        )
        liveLogStore.evaluate()
        await waitForEvaluation(liveLogStore)
        check(
            liveLogStore.display == "1",
            "backspace preserves base-10 semantics in a still-open log call"
        )
        check(
            liveLogStore.history.first?.executionExpression == "log10(10)",
            "re-derived log input keeps the explicit base-10 runtime spelling"
        )
        liveLogStore.clear()
        liveLogStore.appendFunction("ln")
        liveLogStore.append("1")
        liveLogStore.append("0")
        liveLogStore.append("0")
        liveLogStore.evaluate()
        await waitForEvaluation(liveLogStore)
        check(liveLogStore.display == "4.605170185988091", "the ln key keeps the natural logarithm")

        // The visible `log(` token is longer in the executable form (`log10(`).
        // Clearing it one character at a time must not leave hidden runtime
        // input that corrupts the next number.
        liveLogStore.clear()
        liveLogStore.appendFunction("log")
        for _ in 0..<4 {
            liveLogStore.backspace()
        }
        check(liveLogStore.expression.isEmpty, "backspace clears the visible log token")
        liveLogStore.append("2")
        liveLogStore.evaluate()
        await waitForEvaluation(liveLogStore)
        check(liveLogStore.display == "2", "backspace clears the hidden log10 spelling too")

        let liveAutocloseStore = CalculatorStore(runtime: liveRuntime, historyStore: history, clipboard: clipboard)
        liveAutocloseStore.replaceExpression("2*(3+4")
        liveAutocloseStore.evaluate()
        await waitForEvaluation(liveAutocloseStore)
        check(liveAutocloseStore.display == "14", "an unmatched opening parenthesis closes at submission")
        check(
            liveAutocloseStore.history.first?.expression == "2*(3+4)",
            "the submitted expression closes open groups in history too"
        )

        let repeatEqualsStore = CalculatorStore(runtime: liveRuntime, historyStore: history, clipboard: clipboard)
        repeatEqualsStore.replaceExpression("6*7")
        repeatEqualsStore.evaluate()
        await waitForEvaluation(repeatEqualsStore)
        let repeatHistoryCount = repeatEqualsStore.history.count
        repeatEqualsStore.evaluate()
        await waitForEvaluation(repeatEqualsStore)
        check(
            repeatEqualsStore.history.count == repeatHistoryCount,
            "repeating equals on the shown result adds no history row"
        )

        // A slow conversion must not occupy the warm worker: an evaluation
        // submitted while it is in flight still answers first on the shared
        // runtime, because requests are matched by id rather than queued.
        async let slowConversion = liveRuntime.convert(
            value: "12",
            fromUnit: "meter",
            toUnit: "foot",
            precision: 12
        )
        let interleavedEvaluation = try? await liveRuntime.evaluate(expression: "6*7", precision: 16)
        check(interleavedEvaluation?.exact == "42", "evaluation does not queue behind a slower request")
        let completedConversion = try? await slowConversion
        check(completedConversion != nil, "the slower request still completes on the same worker")

        let liveDomainStore = CalculatorStore(runtime: liveRuntime, historyStore: history, clipboard: clipboard)
        let historyCountBeforeDomainError = liveDomainStore.history.count
        liveDomainStore.replaceExpression("1/0")
        liveDomainStore.evaluate()
        await waitForEvaluation(liveDomainStore)
        check(liveDomainStore.expression == "1/0", "live domain failure preserves input")
        check(liveDomainStore.display == "1÷0", "live domain failure does not become a result")
        check(liveDomainStore.history.count == historyCountBeforeDomainError, "live domain failure adds no history")
        check(
            liveDomainStore.errorMessage?.contains("undefined") == true,
            "live core domain error is visible in the app store"
        )

        let factorial = try? await liveRuntime.evaluate(expression: "factorial(5000)", precision: 16)
        check(factorial?.exact?.count == 16_326, "maximum allowed factorial survives the warm app protocol")

        let boundedRuntime = MathRuntimeService(requestTimeout: 0.1)
        do {
            _ = try await boundedRuntime.evaluate(expression: "factorial(5000)^10000", precision: 16)
            check(false, "heavy app calculation must not run past its deadline")
        } catch {
            check(error as? MathRuntimeError == .timedOut, "heavy app calculation returns a timeout")
        }
        let recovered = try? await boundedRuntime.evaluate(expression: "6*7", precision: 16)
        check(recovered?.exact == "42", "app runtime rebuilds after timeout")

        // Abandoning a heavy expression must release the serial local runtime
        // immediately. Keeping conversion requests warm is valuable, but the
        // same policy for CPU-heavy evaluation made the next ordinary result
        // wait for the abandoned operation's ten-second worker-side timeout.
        let cancellationRuntime = MathRuntimeService(requestTimeout: 3)
        let cancellationWarmup = try? await cancellationRuntime.evaluate(
            expression: "1+1",
            precision: 16
        )
        check(cancellationWarmup?.exact == "2", "cancellation runtime starts warm")
        let abandonedEvaluation = Task {
            try? await cancellationRuntime.evaluate(
                expression: "factorial(5000)^10000",
                precision: 16
            )
        }
        try? await Task.sleep(for: .milliseconds(50))
        cancellationRuntime.cancelPendingEvaluation()
        let cancellationRecoveryStart = Date()
        let cancellationRecovery = try? await cancellationRuntime.evaluate(
            expression: "6*7",
            precision: 16
        )
        let cancellationRecoveryElapsed = Date().timeIntervalSince(cancellationRecoveryStart)
        check(cancellationRecovery?.exact == "42", "replacement evaluation succeeds after cancellation")
        check(
            cancellationRecoveryElapsed < 1.5,
            "abandoned evaluation does not occupy the runtime until its timeout"
        )
        _ = await abandonedEvaluation.value

        // A mode transition is also an explicit abandonment boundary. The
        // real app shares one local runtime between expression evaluation and
        // physical conversion, so this composed sequence must cancel the old
        // CPU-heavy request before activating conversion.
        let modeSwitchRequestTimeout: TimeInterval = 3
        let modeSwitchRuntime = MathRuntimeService(requestTimeout: modeSwitchRequestTimeout)
        let modeSwitchWarmup = try? await modeSwitchRuntime.evaluate(
            expression: "1+1",
            precision: 16
        )
        check(modeSwitchWarmup?.exact == "2", "mode-switch runtime starts warm")
        let modeSwitchStore = CalculatorStore(
            runtime: modeSwitchRuntime,
            historyStore: history,
            clipboard: clipboard
        )
        let modeSwitchConversionStore = UnitConversionStore(
            runtime: modeSwitchRuntime,
            clipboard: clipboard
        )
        modeSwitchStore.selectMode(.scientific)
        modeSwitchStore.replaceExpression("factorial(5000)^10000")
        modeSwitchStore.evaluate()
        try? await Task.sleep(for: .milliseconds(50))
        let modeSwitchStart = Date()
        let liveModeTransition = CalculatorModeTransition(popoverSettleDelay: .milliseconds(20))
        liveModeTransition.select(
            .conversion,
            calculatorStore: modeSwitchStore,
            conversionStore: modeSwitchConversionStore
        )
        await waitForConversion(modeSwitchConversionStore)
        let modeSwitchElapsed = Date().timeIntervalSince(modeSwitchStart)
        check(modeSwitchStore.mode == .conversion, "heavy evaluation switches to conversion mode")
        check(!modeSwitchStore.isEvaluating, "mode switch clears calculator progress")
        check(modeSwitchConversionStore.errorMessage == nil, "first conversion survives the mode switch")
        check(modeSwitchConversionStore.output != "—", "first conversion produces a result")
        // This is a cancellation check, not a benchmark of first-use unit
        // conversion on a shared hosted runner. If the old expression keeps
        // the serial worker, this conversion reaches its own request deadline
        // and the result checks above fail. Keep the elapsed guard tied to the
        // same runtime contract instead of imposing a second, undocumented
        // 1.5-second cold-path SLO.
        check(
            modeSwitchElapsed < modeSwitchRequestTimeout,
            "mode switch releases the shared runtime before the old evaluation deadline"
        )

        let warmStart = Date()
        for _ in 0..<20 {
            let result = try? await liveRuntime.evaluate(expression: "6*7", precision: 16)
            check(result?.exact == "42", "live runtime warm result")
        }
        let warmElapsed = Date().timeIntervalSince(warmStart)
        check(warmElapsed < 1.0, "live runtime stays warm between evaluations")

        print(
            "Swift store checks passed: visible/executable expression separation, unary scope, unary edits after percent, "
                + "multiplicative and chained percent, familiar log key semantics, real domain errors, "
                + "large factorial output, stale-result rejection, isolated clipboard, warm runtime reuse "
                + "(20 evaluations in \(Int(warmElapsed * 1_000)) ms), physical conversion, history, memory, "
                + "and failure preservation."
        )
    }

    @MainActor
    private static func waitForEvaluation(_ store: CalculatorStore) async {
        while store.isEvaluating {
            await Task.yield()
        }
    }

    @MainActor
    private static func waitForConversion(_ store: UnitConversionStore) async {
        while store.isConverting {
            await Task.yield()
        }
    }

    @MainActor
    private static func waitUntil(
        timeout: Duration = .seconds(1),
        _ condition: @escaping @MainActor () -> Bool
    ) async {
        let clock = ContinuousClock()
        let deadline = clock.now.advanced(by: timeout)
        while !condition(), clock.now < deadline {
            try? await Task.sleep(for: .milliseconds(5))
        }
    }

    private static func check(_ condition: @autoclosure () -> Bool, _ label: String) {
        guard condition() else {
            fatalError("Swift store check failed: \(label)")
        }
    }
}
