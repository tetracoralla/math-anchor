import Testing
import Foundation
@testable import MathAnchorCore

private struct ImmediateMathRuntime: MathEvaluating {
    let result: EvaluationResult

    func evaluate(expression: String, precision: Int) async throws -> EvaluationResult {
        result
    }
}

private struct DelayedMathRuntime: MathEvaluating {
    func evaluate(expression: String, precision: Int) async throws -> EvaluationResult {
        try? await Task.sleep(for: .milliseconds(80))
        return EvaluationResult(exact: "2", approximate: "2.0")
    }
}

private struct ImmediateUnitRuntime: UnitConverting {
    func convert(
        value: String,
        fromUnit: String,
        toUnit: String,
        precision: Int
    ) async throws -> UnitConversionResult {
        UnitConversionResult(
            exact: fromUnit == "meter" && toUnit == "foot" ? "1250/381" : value,
            approximate: fromUnit == "meter" && toUnit == "foot" ? "3.280839895013123" : value,
            runtimeUnit: toUnit,
            warnings: []
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

private func isolatedHistory() -> (HistoryStore, String) {
    let suite = "MathAnchorCoreTests.\(UUID().uuidString)"
    return (HistoryStore(defaults: UserDefaults(suiteName: suite)!), suite)
}

@Test("Display formatting keeps human notation")
func displayFormattingKeepsHumanNotation() {
    #expect(MathDisplayFormatting.expression("2*pi/3") == "2×π÷3")
}

@Test("Calculator state keeps visible percent notation and exact copy")
@MainActor
func calculatorStateKeepsVisiblePercentAndExactCopy() async {
    let (history, suite) = isolatedHistory()
    defer { UserDefaults.standard.removePersistentDomain(forName: suite) }
    let clipboard = RecordingClipboard()
    let store = CalculatorStore(
        runtime: ImmediateMathRuntime(
            result: EvaluationResult(exact: "sqrt(2)", approximate: "1.414213562373095")
        ),
        historyStore: history,
        clipboard: clipboard
    )

    store.replaceExpression("200+10")
    store.percent()
    #expect(store.expression == "200+10%")

    store.replaceExpression("sqrt(2)")
    store.evaluate()
    while store.isEvaluating { await Task.yield() }
    #expect(store.display == "1.414213562373095")
    #expect(store.distinctExactResult == "sqrt(2)")
    store.copyExactResult()
    #expect(clipboard.value == "sqrt(2)")
}

@Test("Mode change rejects a late evaluation result")
@MainActor
func modeChangeRejectsLateEvaluation() async {
    let (history, suite) = isolatedHistory()
    defer { UserDefaults.standard.removePersistentDomain(forName: suite) }
    let store = CalculatorStore(
        runtime: DelayedMathRuntime(),
        historyStore: history,
        clipboard: RecordingClipboard()
    )

    store.replaceExpression("1+1")
    store.evaluate()
    #expect(store.isEvaluating)
    store.selectMode(.conversion)
    try? await Task.sleep(for: .milliseconds(120))

    #expect(store.mode == .conversion)
    #expect(!store.isEvaluating)
    #expect(store.display == "1+1")
    #expect(store.history.isEmpty)
}

@Test("Physical conversion uses the shared unit runtime")
@MainActor
func physicalConversionUsesSharedRuntime() async {
    let store = UnitConversionStore(
        runtime: ImmediateUnitRuntime(),
        clipboard: RecordingClipboard()
    )

    store.activate()
    while store.isConverting { await Task.yield() }

    #expect(store.sourceUnit == HumanUnitCatalog.meter)
    #expect(store.targetUnit == HumanUnitCatalog.foot)
    #expect(store.output == "3.280839895013123")
    #expect(store.distinctExactResult == "1250/381")
}

private actor CapturingMathRuntime: MathEvaluating {
    var expressions: [String] = []
    let result: EvaluationResult

    init(exact: String, approximate: String) {
        result = EvaluationResult(exact: exact, approximate: approximate)
    }

    func evaluate(expression: String, precision: Int) async throws -> EvaluationResult {
        expressions.append(expression)
        return result
    }
}

@Test("Unary edits and delete preserve an exact result operand", arguments: ["reciprocal", "sign", "function", "delete"])
@MainActor
func exactResultSurvivesEditing(action: String) async {
    let (history, suite) = isolatedHistory()
    defer { UserDefaults.standard.removePersistentDomain(forName: suite) }
    let runtime = CapturingMathRuntime(exact: "1/3", approximate: "0.3333333333333333")
    let store = CalculatorStore(runtime: runtime, historyStore: history)
    store.replaceExpression("1/3")
    store.evaluate()
    while store.isEvaluating { await Task.yield() }
    switch action {
    case "reciprocal": store.reciprocal()
    case "sign": store.toggleSign()
    case "function": store.applyFunction("sin")
    default:
        store.append("+")
        store.append("2")
        store.backspace()
        store.append("3")
    }
    store.evaluate()
    while store.isEvaluating { await Task.yield() }
    let submitted = await runtime.expressions.last!
    #expect(submitted.contains("1/3"))
    #expect(!submitted.contains("0.3333333333333333"))
}

@Test("Exact composite results remain one operand when continued")
@MainActor
func compositeResultIsAtomic() async {
    let (history, suite) = isolatedHistory()
    defer { UserDefaults.standard.removePersistentDomain(forName: suite) }
    let runtime = CapturingMathRuntime(exact: "1 + sqrt(2)", approximate: "2.414213562373095")
    let store = CalculatorStore(runtime: runtime, historyStore: history)
    store.replaceExpression("1+sqrt(2)")
    store.evaluate()
    while store.isEvaluating { await Task.yield() }
    store.append("*")
    store.append("2")
    store.evaluate()
    while store.isEvaluating { await Task.yield() }
    #expect(await runtime.expressions.last == "(1 + sqrt(2))*2")
}

private struct FailingReplacementUnitRuntime: UnitConverting {
    func convert(value: String, fromUnit: String, toUnit: String, precision: Int) async throws -> UnitConversionResult {
        if value != "1" { throw MathRuntimeError.operation("invalid value") }
        return UnitConversionResult(exact: "1/3", approximate: "0.333333333333", runtimeUnit: toUnit, warnings: [])
    }
}

@Test("Pending and failed conversions cannot copy a previous result")
@MainActor
func conversionCopyRequiresCurrentResult() async {
    let clipboard = RecordingClipboard()
    let store = UnitConversionStore(runtime: FailingReplacementUnitRuntime(), clipboard: clipboard)
    store.activate()
    while store.isConverting { await Task.yield() }
    store.appendDigit("2")
    store.copyResult()
    store.copyExactResult()
    #expect(clipboard.value == nil)
    while store.isConverting { await Task.yield() }
    #expect(store.distinctExactResult == nil)
    store.copyExactResult()
    #expect(clipboard.value == nil)
}

@Test("Swapping during a pending conversion preserves the entered value")
@MainActor
func conversionSwapDoesNotUseStaleResult() async {
    let store = UnitConversionStore(runtime: ImmediateUnitRuntime())
    store.activate()
    while store.isConverting { await Task.yield() }
    store.appendDigit("2")
    store.swapUnits()
    #expect(store.input == "12")
    while store.isConverting { await Task.yield() }
}

@Test("Angle choice changes circular functions, not hyperbolic functions or bound values")
func angleProjectionPreservesFunctionMeaning() {
    #expect(ExpressionEditing.evaluationExpression(forVisible: "sin(30)", angleUnit: .degrees) == "sin((30)*pi/180)")
    #expect(ExpressionEditing.evaluationExpression(forVisible: "asin(1/2)", angleUnit: .degrees) == "(asin(1/2)*180/pi)")
    #expect(ExpressionEditing.evaluationExpression(forVisible: "sinh(1)", angleUnit: .degrees) == "sinh(1)")
    var expression = CalculatorExpression()
    expression.angleUnit = .degrees
    let result = expression.bind(visible: "0.5", evaluation: "sin(pi/6)")
    expression.source = "asin(\(result))"
    #expect(expression.evaluation == "(asin((sin(pi/6)))*180/pi)")
}

@Test("Trig detection tolerates coefficient adjacency and rejects hyperbolic names")
func angleDetectionBoundaries() {
    #expect(AngleUnit.applies(to: "sin(30)"))
    #expect(AngleUnit.applies(to: "2*sin(30)"))
    #expect(AngleUnit.applies(to: "2sin(30)"))
    #expect(AngleUnit.applies(to: "asin(1/2)+1"))
    #expect(AngleUnit.applies(to: "-tan(45)"))
    #expect(!AngleUnit.applies(to: "sinh(3)"))
    #expect(!AngleUnit.applies(to: "asinh(3)"))
    #expect(!AngleUnit.applies(to: "log(100)"))
    #expect(!AngleUnit.applies(to: "5+2"))
}

@Test("Percent expansion inside a still-open group keeps its prefix")
func percentInsideOpenGroupKeepsPrefix() {
    #expect(ExpressionEditing.evaluationExpression(forVisible: "cos(30%") == "cos((30)/100")
    #expect(ExpressionEditing.evaluationExpression(forVisible: "cos(5+30%") == "cos(5+((5)*(30)/100)")
    #expect(ExpressionEditing.evaluationExpression(forVisible: "cos(30%)") == "cos((30)/100)")
    #expect(ExpressionEditing.evaluationExpression(forVisible: "cos(5+30%)") == "cos(5+((5)*(30)/100))")
    #expect(ExpressionEditing.evaluationExpression(forVisible: "10%") == "(10)/100")
}

@Test("Angle meaning persists with history and restores with the value")
@MainActor
func angleHistoryRoundTrip() async {
    let (history, suite) = isolatedHistory()
    defer { UserDefaults.standard.removePersistentDomain(forName: suite) }
    let runtime = CapturingMathRuntime(exact: "1/2", approximate: "0.5")
    let store = CalculatorStore(runtime: runtime, historyStore: history)
    store.selectAngleUnit(.degrees)
    store.replaceExpression("sin(30")
    store.evaluate()
    while store.isEvaluating { await Task.yield() }
    let entry = history.load().first!
    #expect(entry.angleUnit == .degrees)
    #expect(entry.executionExpression == "sin((30)*pi/180)")
    store.selectAngleUnit(.radians)
    store.restore(entry)
    #expect(store.angleUnit == .degrees)
    store.reciprocal()
    store.evaluate()
    while store.isEvaluating { await Task.yield() }
    #expect(await runtime.expressions.last == "1/((1/2))")
}

private struct SlowUnitRuntime: UnitConverting {
    func convert(value: String, fromUnit: String, toUnit: String, precision: Int) async throws -> UnitConversionResult {
        try? await Task.sleep(for: .milliseconds(50))
        return UnitConversionResult(exact: value, approximate: value, runtimeUnit: toUnit, warnings: [])
    }
}

@Test("Leaving Convert cancels the draft and ignores late completion")
@MainActor
func leavingConversionInvalidatesPendingResult() async {
    let store = UnitConversionStore(runtime: SlowUnitRuntime())
    store.activate()
    await Task.yield()
    store.deactivate()
    try? await Task.sleep(for: .milliseconds(90))
    #expect(!store.isConverting)
    #expect(store.output == "—")
    store.activate()
    while store.isConverting { await Task.yield() }
    #expect(store.hasCurrentResult)
}

private struct ExponentUnitRuntime: UnitConverting {
    func convert(value: String, fromUnit: String, toUnit: String, precision: Int) async throws -> UnitConversionResult {
        UnitConversionResult(exact: nil, approximate: "1e+20", runtimeUnit: toUnit, warnings: [])
    }
}

@Test("Digits after swap start an entry instead of editing an exponent")
@MainActor
func swappedExponentStartsNewEntry() async {
    let store = UnitConversionStore(runtime: ExponentUnitRuntime())
    store.activate()
    while store.isConverting { await Task.yield() }
    store.swapUnits()
    while store.isConverting { await Task.yield() }
    store.appendDigit("2")
    #expect(store.input == "2")
    store.deactivate()
}

@Test("Unary keys edit the pending operand inside an open function")
@MainActor
func nestedUnaryEditingStaysInsideOpenFunction() {
    let (history, suite) = isolatedHistory()
    defer { UserDefaults.standard.removePersistentDomain(forName: suite) }
    let store = CalculatorStore(historyStore: history)
    store.replaceExpression("cos(30")
    store.toggleSign()
    #expect(store.expression == "cos(-30")
    store.toggleSign()
    #expect(store.expression == "cos(30")
    store.applyFunction("sqrt")
    #expect(store.expression == "cos(sqrt(30)")
    store.replaceExpression("2*(5+3")
    store.reciprocal()
    #expect(store.expression == "2*(5+1/(3)")
}

@Test("Negated degree calls retain angle semantics")
func negatedDegreeFunctions() {
    #expect(ExpressionEditing.evaluationExpression(forVisible: "-sin(30)", angleUnit: .degrees) == "-sin((30)*pi/180)")
    #expect(ExpressionEditing.evaluationExpression(forVisible: "-(cos(60)+sin(30))", angleUnit: .degrees) == "-(cos((60)*pi/180)+sin((30)*pi/180))")
}

@Test("Rejected close-parenthesis does not discard the displayed result")
@MainActor
func unmatchedCloseAfterResultIsIgnored() async {
    let (history, suite) = isolatedHistory()
    defer { UserDefaults.standard.removePersistentDomain(forName: suite) }
    let store = CalculatorStore(runtime: ImmediateMathRuntime(result: EvaluationResult(exact: "2", approximate: "2")), historyStore: history)
    store.replaceExpression("1+1")
    store.evaluate()
    while store.isEvaluating { await Task.yield() }
    store.append(")")
    #expect(store.expression == "1+1")
    #expect(store.isShowingResult)
    store.append("+")
    store.append("1")
    #expect(store.expression == "2+1")
}

private final class CurrencyValueProbe: CurrencyConverting, @unchecked Sendable {
    private let lock = NSLock()
    private var capturedValue: String?
    var value: String? { lock.withLock { capturedValue } }

    func convertCurrency(value: String, fromCurrency: String, toCurrency: String, precision: Int, forceRefresh: Bool) async throws -> CurrencyConversionResult {
        lock.withLock { capturedValue = value }
        throw MathRuntimeError.operation("Test provider unavailable")
    }
}

@Test("Switching a swapped physical value to currency sends decimal input")
@MainActor
func physicalToCurrencyUsesDecimalAmount() async {
    let currency = CurrencyValueProbe()
    let store = UnitConversionStore(runtime: ImmediateUnitRuntime(), currencyRuntime: currency)
    store.activate()
    while store.isConverting { await Task.yield() }
    store.swapUnits()
    while store.isConverting { await Task.yield() }
    store.selectSource(HumanUnitCatalog.usDollar)
    while store.isConverting { await Task.yield() }
    #expect(currency.value == "3.280839895013123")
}

@Test("Memory completes open functions and preserves exact values through edits")
@MainActor
func memoryPreservesBoundValues() async {
    let (history, suite) = isolatedHistory()
    defer { UserDefaults.standard.removePersistentDomain(forName: suite) }
    let runtime = CapturingMathRuntime(exact: "1/3", approximate: "0.3333333333333333")
    let store = CalculatorStore(runtime: runtime, historyStore: history)
    store.replaceExpression("1/3")
    store.evaluate()
    while store.isEvaluating { await Task.yield() }
    store.memoryAdd()
    store.clear()
    store.memoryRecall()
    store.reciprocal()
    store.evaluate()
    while store.isEvaluating { await Task.yield() }
    #expect(await runtime.expressions.last == "1/((1/3))")
    store.memoryClear()
    store.selectAngleUnit(.degrees)
    store.replaceExpression("sin(30")
    store.memoryAdd()
    #expect(store.memory == "sin(30)")
    store.clear()
    store.memoryRecall()
    store.evaluate()
    while store.isEvaluating { await Task.yield() }
    #expect(await runtime.expressions.last == "(sin((30)*pi/180))")
}

@Test("Undoing a unary edit does not restore a hidden old angle setting")
@MainActor
func undoRetainsVisibleAngleSetting() async {
    let (history, suite) = isolatedHistory()
    defer { UserDefaults.standard.removePersistentDomain(forName: suite) }
    let runtime = CapturingMathRuntime(exact: "0", approximate: "0")
    let store = CalculatorStore(runtime: runtime, historyStore: history)
    store.selectAngleUnit(.degrees)
    store.replaceExpression("sin(30)")
    store.square()
    store.selectAngleUnit(.radians)
    store.backspace()
    store.evaluate()
    while store.isEvaluating { await Task.yield() }
    #expect(await runtime.expressions.last == "sin(30)")
    #expect(store.history.first?.angleUnit == .radians)
}

@Test("Legacy trigonometric history keeps its original radians meaning")
func legacyHistoryRetainsRadians() {
    let (history, suite) = isolatedHistory()
    defer { UserDefaults.standard.removePersistentDomain(forName: suite) }
    history.save([HistoryEntry(expression: "sin(30)", exact: "sin(30)", result: "-0.9880316240928618")])
    #expect(history.load().first?.angleUnit == .radians)
}
