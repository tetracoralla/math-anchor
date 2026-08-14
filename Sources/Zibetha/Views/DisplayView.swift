import SwiftUI

struct DisplayView: View {
    @ObservedObject var store: CalculatorStore

    var body: some View {
        VStack(alignment: .trailing, spacing: 3) {
            HStack(alignment: .firstTextBaseline, spacing: 7) {
                if store.memory != nil {
                    Text("M")
                        .font(.system(size: 9, weight: .bold, design: .rounded))
                        .foregroundStyle(CalculatorPalette.accent)
                        .padding(.horizontal, 5)
                        .frame(height: 16)
                        .background {
                            Capsule()
                                .fill(CalculatorPalette.controlActive)
                        }
                        .accessibilityLabel("Memory contains a value")
                }

                Spacer(minLength: 0)

                if store.isShowingResult {
                    Text(store.expressionForDisplay)
                        .font(.system(size: 14, weight: .medium, design: .rounded))
                        .foregroundStyle(CalculatorPalette.secondaryText)
                        .lineLimit(1)
                        .truncationMode(.head)
                        .accessibilityLabel("Expression")
                        .accessibilityValue(store.expressionForDisplay)
                }
            }
            .frame(height: 16)

            Text(store.isEvaluating ? "…" : store.display)
                .font(.system(size: 40, weight: .light, design: .rounded))
                .monospacedDigit()
                .lineLimit(1)
                .minimumScaleFactor(0.28)
                .frame(maxWidth: .infinity, alignment: .trailing)
                .contentTransition(.numericText())
                .accessibilityLabel(store.isShowingResult ? "Result" : "Expression")
                .accessibilityValue(store.display)
                .contextMenu {
                    Button("Copy Result", action: store.copyResult)
                    if store.distinctExactResult != nil {
                        Button("Copy Exact Value", action: store.copyExactResult)
                    }
                }

            if let errorMessage = store.errorMessage {
                Text(errorMessage)
                    .font(.system(size: 10, weight: .semibold, design: .rounded))
                    .foregroundStyle(CalculatorPalette.error)
                    .lineLimit(1)
                    .frame(maxWidth: .infinity, alignment: .trailing)
                    .accessibilityLabel("Error")
                    .frame(height: 15)
            }
        }
        .foregroundStyle(CalculatorPalette.primaryText)
        .padding(.horizontal, 14)
        .padding(.vertical, 12)
        .frame(height: 110, alignment: .bottom)
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
        .frame(height: CalculatorLayout.displayHeight, alignment: .bottom)
    }
}
