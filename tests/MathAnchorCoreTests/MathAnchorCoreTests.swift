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
