import Combine
import Foundation

@MainActor
package final class CalculatorModeTransition: ObservableObject {
    private let popoverSettleDelay: Duration
    private var pendingAction: Task<Void, Never>?

    package init(popoverSettleDelay: Duration = .milliseconds(250)) {
        self.popoverSettleDelay = popoverSettleDelay
    }

    package func toggleModeMenu(
        calculatorStore: CalculatorStore,
        conversionStore: UnitConversionStore
    ) {
        if calculatorStore.isModePopoverPresented {
            pendingAction?.cancel()
            pendingAction = nil
            calculatorStore.isModePopoverPresented = false
            return
        }

        let mustWait = conversionStore.activePopover != nil
            || conversionStore.isPopoverDismissalSettling(for: popoverSettleDelay)
            || pendingAction != nil
        conversionStore.dismissActivePopover()
        pendingAction?.cancel()
        pendingAction = nil

        guard mustWait else {
            calculatorStore.isModePopoverPresented = true
            return
        }

        // AppKit removes a SwiftUI popover asynchronously. Keep its conversion
        // anchor mounted until the close animation has settled, then present
        // the mode popover. Presenting both in the same update can orphan the
        // first NSPanel even though it has already left the AX tree.
        deferAction { [weak calculatorStore] in
            calculatorStore?.isModePopoverPresented = true
        }
    }

    package func select(
        _ mode: CalculatorMode,
        calculatorStore: CalculatorStore,
        conversionStore: UnitConversionStore
    ) {
        let mustWait = calculatorStore.mode == .conversion
            && mode != .conversion
            && (
                conversionStore.activePopover != nil
                    || conversionStore.isPopoverDismissalSettling(for: popoverSettleDelay)
                    || pendingAction != nil
            )
        conversionStore.dismissActivePopover()
        calculatorStore.isModePopoverPresented = false
        pendingAction?.cancel()
        pendingAction = nil

        guard mustWait else {
            apply(
                mode,
                calculatorStore: calculatorStore,
                conversionStore: conversionStore
            )
            return
        }

        // The same ordering is required for menu/shortcut selection, where
        // AppKit may have begun dismissing the popover before this action runs.
        deferAction { [weak self, weak calculatorStore, weak conversionStore] in
            guard let self, let calculatorStore, let conversionStore else { return }
            self.apply(
                mode,
                calculatorStore: calculatorStore,
                conversionStore: conversionStore
            )
        }
    }

    private func deferAction(_ action: @escaping @MainActor () -> Void) {
        let delay = popoverSettleDelay
        pendingAction = Task { @MainActor [weak self] in
            do {
                try await Task.sleep(for: delay)
            } catch {
                return
            }
            guard !Task.isCancelled, let self else { return }
            self.pendingAction = nil
            action()
        }
    }

    private func apply(
        _ mode: CalculatorMode,
        calculatorStore: CalculatorStore,
        conversionStore: UnitConversionStore
    ) {
        calculatorStore.selectMode(mode)
        if mode == .conversion {
            conversionStore.activate()
        }
    }
}
