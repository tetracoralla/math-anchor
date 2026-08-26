import Combine
import Foundation

package enum ConversionPopover: Equatable {
    case sourceUnit
    case targetUnit
    case rateDetails
}

@MainActor
package final class UnitConversionStore: ObservableObject {
    @Published package private(set) var input = "1"
    @Published package private(set) var output = "—"
    @Published package private(set) var sourceUnit = HumanUnitCatalog.meter
    @Published package private(set) var targetUnit = HumanUnitCatalog.foot
    @Published package private(set) var isConverting = false
    @Published package private(set) var errorMessage: String?
    @Published package private(set) var distinctExactResult: String?
    @Published package private(set) var rateMetadata: CurrencyRateMetadata?
    @Published package private(set) var rateMessage: String?
    @Published package private(set) var activePopover: ConversionPopover? {
        didSet {
            if oldValue != nil, activePopover == nil {
                lastPopoverDismissal = popoverClock.now
            }
        }
    }
    @Published package private(set) var isShowingDelayedProgress = false

    private let runtime: any UnitConverting
    private let currencyRuntime: (any CurrencyConverting)?
    private let clipboard: any ClipboardWriting
    private var revision = 0
    private var activeRequestID: UUID?
    private var scheduledTask: Task<Void, Never>?
    private var progressTask: Task<Void, Never>?
    private var inputComesFromResult = false
    private var completedSourceUnit: UnitDefinition?
    private var completedTargetUnit: UnitDefinition?
    private let popoverClock = ContinuousClock()
    private var lastPopoverDismissal: ContinuousClock.Instant?

    package init(
        runtime: any UnitConverting,
        currencyRuntime: (any CurrencyConverting)? = nil,
        clipboard: (any ClipboardWriting)? = nil
    ) {
        self.runtime = runtime
        self.currencyRuntime = currencyRuntime
        self.clipboard = clipboard ?? SystemClipboard()
    }

    package var sourceChoices: [UnitDefinition] {
        HumanUnitCatalog.all
    }

    package var targetChoices: [UnitDefinition] {
        HumanUnitCatalog.units(in: sourceUnit.category)
    }

    package var resultForDisplay: String {
        isShowingDelayedProgress || (isConverting && output == "—")
            ? "…"
            : ConversionDisplayFormatting.value(output)
    }

    /// True only while the first result for the current units is still
    /// pending; value-only refreshes keep the previous result visible.
    package var isAwaitingFirstResult: Bool {
        isConverting && output == "—"
    }

    package var isCurrencyConversion: Bool {
        sourceUnit.isCurrency
    }

    package var inputForDisplay: String {
        inputComesFromResult ? ConversionDisplayFormatting.value(input) : input
    }

    package func activate() {
        guard output == "—", !isConverting else { return }
        scheduleConversion(immediate: true)
    }

    package func appendDigit(_ digit: String) {
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

    package func appendDecimal() {
        prepareInputForEditing()
        guard !input.contains("."), input.count < 18 else { return }
        input.append(".")
        scheduleConversion()
    }

    package func toggleSign() {
        prepareInputForEditing()
        guard input != "0" else { return }
        if input.hasPrefix("-") {
            input.removeFirst()
        } else {
            input.insert("-", at: input.startIndex)
        }
        scheduleConversion()
    }

    package func backspace() {
        prepareInputForEditing()
        guard input != "0" else { return }
        input.removeLast()
        if input.isEmpty || input == "-" {
            input = "0"
        }
        scheduleConversion()
    }

    package func clear() {
        input = "0"
        inputComesFromResult = false
        scheduleConversion(immediate: true)
    }

    package func selectSource(_ unit: UnitDefinition) {
        guard unit != sourceUnit else { return }
        activePopover = nil
        sourceUnit = unit
        if targetUnit.category != unit.category || targetUnit == unit {
            targetUnit = HumanUnitCatalog.alternate(to: unit)
        }
        scheduleConversion(immediate: true)
    }

    package func selectTarget(_ unit: UnitDefinition) {
        guard unit.category == sourceUnit.category, unit != targetUnit else { return }
        activePopover = nil
        targetUnit = unit
        scheduleConversion(immediate: true)
    }

    package func swapUnits() {
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

    package func refreshNow() {
        scheduleConversion(immediate: true)
    }

    package func refreshRates() {
        guard isCurrencyConversion else { return }
        activePopover = nil
        scheduleConversion(immediate: true, forceCurrencyRefresh: true)
    }

    package func setPopover(_ popover: ConversionPopover, presented: Bool) {
        if presented {
            activePopover = popover
        } else if activePopover == popover {
            activePopover = nil
        }
    }

    @discardableResult
    package func dismissActivePopover() -> Bool {
        guard activePopover != nil else { return false }
        activePopover = nil
        return true
    }

    package func isPopoverDismissalSettling(for duration: Duration) -> Bool {
        guard let lastPopoverDismissal else { return false }
        return lastPopoverDismissal.duration(to: popoverClock.now) < duration
    }

    package func copyResult() {
        guard output != "—", errorMessage == nil else { return }
        clipboard.write(output)
    }

    package func copyExactResult() {
        guard let distinctExactResult else { return }
        clipboard.write(distinctExactResult)
    }

    private func scheduleConversion(
        immediate: Bool = false,
        forceCurrencyRefresh: Bool = false
    ) {
        scheduledTask?.cancel()
        progressTask?.cancel()
        isShowingDelayedProgress = false
        revision &+= 1
        let submittedRevision = revision
        let requestID = UUID()
        activeRequestID = requestID
        isConverting = true
        errorMessage = nil
        let submittedSource = sourceUnit
        let submittedTarget = targetUnit
        // A value-only edit keeps the previous result, exact value, and rate
        // metadata on screen until the replacement lands; wiping them per
        // keystroke turned every key into an old-value → "…" → new-value
        // flash and churned the currency footer through UPDATING.
        let keepsPriorResult =
            output != "—"
            && submittedSource == completedSourceUnit
            && submittedTarget == completedTargetUnit
            && !forceCurrencyRefresh
        if !keepsPriorResult {
            distinctExactResult = nil
            output = "—"
            rateMetadata = nil
            rateMessage = nil
        } else {
            // Preserve a warm-path result without flashing, but never leave a
            // new input paired with an old output indefinitely. Once the
            // replacement takes longer than a few frames, surface progress.
            progressTask = Task { [weak self] in
                try? await Task.sleep(for: .milliseconds(180))
                guard !Task.isCancelled, let self,
                      self.isCurrent(requestID, revision: submittedRevision)
                else { return }
                self.isShowingDelayedProgress = true
            }
        }
        let submittedInput = normalizedInput
        let submittedForCurrency = submittedSource.isCurrency

        scheduledTask = Task { [weak self] in
            if !immediate {
                try? await Task.sleep(for: .milliseconds(110))
            }
            guard !Task.isCancelled, let self else { return }
            do {
                if submittedForCurrency {
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
                    self.finishProgress()
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
                    let result = try await self.runtime.convert(
                        value: submittedInput,
                        fromUnit: submittedSource.runtimeUnit,
                        toUnit: submittedTarget.runtimeUnit,
                        precision: 12
                    )
                    guard self.isCurrent(requestID, revision: submittedRevision) else { return }
                    self.activeRequestID = nil
                    self.isConverting = false
                    self.finishProgress()
                    self.output = result.displayValue
                    self.distinctExactResult = result.distinctExactValue
                }
                self.completedSourceUnit = submittedSource
                self.completedTargetUnit = submittedTarget
            } catch {
                guard self.isCurrent(requestID, revision: submittedRevision) else { return }
                self.activeRequestID = nil
                self.isConverting = false
                self.finishProgress()
                self.output = "—"
                self.completedSourceUnit = nil
                self.completedTargetUnit = nil
                if submittedForCurrency {
                    self.rateMetadata = nil
                    self.rateMessage = nil
                }
                if error as? MathRuntimeError != .cancelled {
                    self.errorMessage = submittedForCurrency
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

    private func finishProgress() {
        progressTask?.cancel()
        progressTask = nil
        isShowingDelayedProgress = false
    }
}
