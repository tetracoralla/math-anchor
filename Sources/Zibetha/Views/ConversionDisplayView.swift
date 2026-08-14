import SwiftUI

struct ConversionDisplayView: View {
    @ObservedObject var store: UnitConversionStore

    var body: some View {
        VStack(spacing: 0) {
            valueRow(
                value: store.inputForDisplay,
                unit: store.sourceUnit,
                choices: store.sourceChoices,
                popover: .sourceUnit,
                accessibilityLabel: "Source value",
                pickerAccessibilityLabel: store.isCurrencyConversion
                    ? "Source currency"
                    : "Source unit",
                onSelect: store.selectSource
            )

            directionDivider

            valueRow(
                value: store.resultForDisplay,
                unit: store.targetUnit,
                choices: store.targetChoices,
                popover: .targetUnit,
                accessibilityLabel: "Converted value",
                pickerAccessibilityLabel: store.isCurrencyConversion
                    ? "Target currency"
                    : "Target unit",
                onSelect: store.selectTarget
            )
            .contextMenu {
                Button("Copy Result", action: store.copyResult)
                if store.distinctExactResult != nil {
                    Button("Copy Exact Value", action: store.copyExactResult)
                }
            }

            statusFooter
        }
        .accessibilityElement(children: .contain)
        .foregroundStyle(CalculatorPalette.primaryText)
        .padding(.horizontal, 13)
        .padding(.vertical, 10)
        .frame(height: CalculatorLayout.conversionPanelHeight)
        .background {
            RoundedRectangle(cornerRadius: 19, style: .continuous)
                .fill(CalculatorPalette.display)
                .overlay {
                    RoundedRectangle(cornerRadius: 19, style: .continuous)
                        .strokeBorder(CalculatorPalette.border, lineWidth: 0.75)
                }
                .shadow(color: .black.opacity(0.10), radius: 4, y: 2)
        }
        .padding(.horizontal, CalculatorLayout.contentInset)
        .frame(height: CalculatorLayout.conversionDisplayHeight, alignment: .bottom)
    }

    private func valueRow(
        value: String,
        unit: UnitDefinition,
        choices: [UnitDefinition],
        popover: ConversionPopover,
        accessibilityLabel: String,
        pickerAccessibilityLabel: String,
        onSelect: @escaping (UnitDefinition) -> Void
    ) -> some View {
        HStack(alignment: .bottom, spacing: 10) {
            UnitPickerView(
                selection: unit,
                units: choices,
                pickerAccessibilityLabel: pickerAccessibilityLabel,
                isPresented: popoverBinding(for: popover),
                onSelect: onSelect
            )

            Spacer(minLength: 8)

            Text(value)
                .font(.system(size: 30, weight: .light, design: .rounded))
                .monospacedDigit()
                .lineLimit(1)
                .minimumScaleFactor(0.42)
                .frame(maxWidth: .infinity, alignment: .trailing)
                .contentTransition(.numericText())
                .accessibilityLabel(accessibilityLabel)
                .accessibilityValue(value)
        }
        .frame(height: 50)
        .accessibilityElement(children: .contain)
    }

    private func popoverBinding(for popover: ConversionPopover) -> Binding<Bool> {
        Binding(
            get: { store.activePopover == popover },
            set: { store.setPopover(popover, presented: $0) }
        )
    }

    private var directionDivider: some View {
        HStack(spacing: 8) {
            Rectangle()
                .fill(CalculatorPalette.border)
                .frame(height: 0.75)

            Image(systemName: "arrow.down")
                .font(.system(size: 9, weight: .bold))
                .foregroundStyle(CalculatorPalette.secondaryText)
                .frame(width: 12)

            Rectangle()
                .fill(CalculatorPalette.border)
                .frame(height: 0.75)
        }
        .frame(height: 16)
        .accessibilityHidden(true)
    }

    @ViewBuilder
    private var statusFooter: some View {
        if store.isCurrencyConversion {
            CurrencyRateStatusView(store: store)
                .frame(height: 20)
        } else if let errorMessage = store.errorMessage {
            Text(errorMessage)
                .font(.system(size: 9, weight: .semibold, design: .rounded))
                .foregroundStyle(CalculatorPalette.error)
                .frame(maxWidth: .infinity, alignment: .trailing)
                .frame(height: 20)
                .accessibilityLabel("Error")
        } else {
            Color.clear
                .frame(height: 20)
                .accessibilityHidden(true)
        }
    }
}
