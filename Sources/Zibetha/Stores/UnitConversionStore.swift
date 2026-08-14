import Combine
import Foundation

enum ConversionPopover: Equatable {
    case sourceUnit
    case targetUnit
    case rateDetails
}

@MainActor
final class UnitConversionStore: ObservableObject {
    @Published private(set) var input = "1"
    @Published private(set) var output = "—"
    @Published private(set) var sourceUnit = HumanUnitCatalog.meter
    @Published private(set) var targetUnit = HumanUnitCatalog.foot
    @Published private(set) var isConverting = false
    @Published private(set) var errorMessage: String?
    @Published private(set) var distinctExactResult: String?
    @Published private(set) var rateMetadata: CurrencyRateMetadata?
    @Published private(set) var rateMessage: String?
    @Published private(set) var activePopover: ConversionPopover?

    private let runtime: any UnitConverting
    private let currencyRuntime: (any CurrencyConverting)?
    private let clipboard: any ClipboardWriting
    private var revision = 0
    private var activeRequestID: UUID?
    private var scheduledTask: Task<Void, Never>?
    private var inputComesFromResult = false

    init(
        runtime: any UnitConverting,
        currencyRuntime: (any CurrencyConverting)? = nil,
        clipboard: (any ClipboardWriting)? = nil
    ) {
        self.runtime = runtime
        self.currencyRuntime = currencyRuntime
        self.clipboard = clipboard ?? SystemClipboard()
    }

    var sourceChoices: [UnitDefinition] {
        HumanUnitCatalog.all
    }

    var targetChoices: [UnitDefinition] {
        HumanUnitCatalog.units(in: sourceUnit.category)
    }

    var resultForDisplay: String {
        isConverting && output == "—"
            ? "…"
            : ConversionDisplayFormatting.value(output)
    }

    var isCurrencyConversion: Bool {
        sourceUnit.isCurrency
    }

    var inputForDisplay: String {
        inputComesFromResult ? ConversionDisplayFormatting.value(input) : input
    }

    func activate() {
        guard output == "—", !isConverting else { return }
        scheduleConversion(immediate: true)
    }

    func appendDigit(_ digit: String) {
        guard digit.count == 1, digit.first?.isNumber == true else { return }
        prepareInputForEditing()
        guard input.count < 18 else { return }
        if input == "0" {
            input = digit
        } else if input == "-0" {
            input = "-" + digit
        } else {
            input.append(digit)
        }
        scheduleConversion()
    }

    func appendDecimal() {
        prepareInputForEditing()
        guard !input.contains("."), input.count < 18 else { return }
        input.append(".")
        scheduleConversion()
    }

    func toggleSign() {
        prepareInputForEditing()
        guard input != "0" else { return }
        if input.hasPrefix("-") {
            input.removeFirst()
        } else {
            input.insert("-", at: input.startIndex)
        }
        scheduleConversion()
    }

    func backspace() {
        prepareInputForEditing()
        guard input != "0" else { return }
        input.removeLast()
        if input.isEmpty || input == "-" {
            input = "0"
        }
        scheduleConversion()
    }

    func clear() {
        input = "0"
        inputComesFromResult = false
        scheduleConversion(immediate: true)
    }

    func selectSource(_ unit: UnitDefinition) {
        guard unit != sourceUnit else { return }
        activePopover = nil
        sourceUnit = unit
        if targetUnit.category != unit.category || targetUnit == unit {
            targetUnit = HumanUnitCatalog.alternate(to: unit)
        }
        scheduleConversion(immediate: true)
    }

    func selectTarget(_ unit: UnitDefinition) {
        guard unit.category == sourceUnit.category, unit != targetUnit else { return }
        activePopover = nil
        targetUnit = unit
        scheduleConversion(immediate: true)
    }

    func swapUnits() {
        guard sourceUnit.category == targetUnit.category else { return }
        let previousSource = sourceUnit
        sourceUnit = targetUnit
        targetUnit = previousSource
        if output != "—", errorMessage == nil {
            input = output
            inputComesFromResult = true
        }
        scheduleConversion(immediate: true)
    }

    func refreshNow() {
        scheduleConversion(immediate: true)
    }

    func refreshRates() {
        guard isCurrencyConversion else { return }
        activePopover = nil
        scheduleConversion(immediate: true, forceCurrencyRefresh: true)
    }

    func setPopover(_ popover: ConversionPopover, presented: Bool) {
        if presented {
            activePopover = popover
        } else if activePopover == popover {
            activePopover = nil
        }
    }

    @discardableResult
    func dismissActivePopover() -> Bool {
        guard activePopover != nil else { return false }
        activePopover = nil
        return true
    }

    func copyResult() {
        guard output != "—", errorMessage == nil else { return }
        clipboard.write(output)
    }

    func copyExactResult() {
        guard let distinctExactResult else { return }
        clipboard.write(distinctExactResult)
    }

    private func scheduleConversion(
        immediate: Bool = false,
        forceCurrencyRefresh: Bool = false
    ) {
        scheduledTask?.cancel()
        runtime.cancelPendingConversion()
        currencyRuntime?.cancelPendingCurrencyConversion()
        revision &+= 1
        let submittedRevision = revision
        let requestID = UUID()
        activeRequestID = requestID
        isConverting = true
        errorMessage = nil
        distinctExactResult = nil
        output = "—"
        rateMetadata = nil
        rateMessage = nil
        let submittedInput = normalizedInput
        let submittedSource = sourceUnit
        let submittedTarget = targetUnit

        scheduledTask = Task { [weak self] in
            if !immediate {
                try? await Task.sleep(for: .milliseconds(110))
            }
            guard !Task.isCancelled, let self else { return }
            do {
                if submittedSource.isCurrency {
                    guard let currencyRuntime = self.currencyRuntime else {
                        throw MathRuntimeError.operation("Currency rates are unavailable.")
                    }
                    let result = try await currencyRuntime.convertCurrency(
                        value: submittedInput,
                        fromCurrency: submittedSource.runtimeUnit,
                        toCurrency: submittedTarget.runtimeUnit,
                        precision: 12,
                        forceRefresh: forceCurrencyRefresh
                    )
                    guard self.isCurrent(requestID, revision: submittedRevision) else { return }
                    self.activeRequestID = nil
                    self.isConverting = false
                    self.output = result.displayValue
                    self.rateMetadata = result.rate
                    if result.rate.refreshFailed {
                        self.rateMessage = "Refresh failed; using cached rates."
                    } else if result.rate.refreshDeferred {
                        self.rateMessage = "Using the latest available rate; refresh will retry automatically."
                    } else {
                        self.rateMessage = nil
                    }
                } else {
                    let result = try await runtime.convert(
                        value: submittedInput,
                        fromUnit: submittedSource.runtimeUnit,
                        toUnit: submittedTarget.runtimeUnit,
                        precision: 12
                    )
                    guard self.isCurrent(requestID, revision: submittedRevision) else { return }
                    self.activeRequestID = nil
                    self.isConverting = false
                    self.output = result.displayValue
                    self.distinctExactResult = result.distinctExactValue
                }
            } catch {
                guard self.isCurrent(requestID, revision: submittedRevision) else { return }
                self.activeRequestID = nil
                self.isConverting = false
                self.output = "—"
                if submittedSource.isCurrency {
                    self.rateMetadata = nil
                    self.rateMessage = nil
                }
                if error as? MathRuntimeError != .cancelled {
                    self.errorMessage = submittedSource.isCurrency
                        ? "Rates unavailable"
                        : "Conversion unavailable"
                }
            }
        }
    }

    private var normalizedInput: String {
        input.hasSuffix(".") ? String(input.dropLast()) : input
    }

    private func prepareInputForEditing() {
        guard inputComesFromResult else { return }
        input = ConversionDisplayFormatting.value(input)
        inputComesFromResult = false
    }

    private func isCurrent(_ id: UUID, revision: Int) -> Bool {
        activeRequestID == id && self.revision == revision
    }
}
