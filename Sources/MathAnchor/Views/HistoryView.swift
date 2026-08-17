import SwiftUI

struct HistoryView: View {
    @ObservedObject var store: CalculatorStore

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Text("History")
                    .font(.system(size: 14, weight: .bold, design: .rounded))
                Spacer()
                Button("Clear", action: store.clearHistory)
                    .font(.system(size: 11, weight: .semibold, design: .rounded))
                    .foregroundStyle(CalculatorPalette.accent)
                    .buttonStyle(.plain)
                    .disabled(store.history.isEmpty)
                    .opacity(store.history.isEmpty ? 0.34 : 1)
            }
            .foregroundStyle(CalculatorPalette.primaryText)
            .padding(.horizontal, 16)
            .frame(height: CalculatorLayout.headerHeight)

            Rectangle()
                .fill(CalculatorPalette.border)
                .frame(height: 1)

            if store.history.isEmpty {
                VStack(spacing: 8) {
                    Image(systemName: "clock.arrow.circlepath")
                        .font(.system(size: 21, weight: .regular))
                    Text("No History")
                        .font(.system(size: 12, weight: .medium, design: .rounded))
                }
                .foregroundStyle(CalculatorPalette.secondaryText)
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else {
                ScrollView {
                    LazyVStack(spacing: 7) {
                        ForEach(store.history) { entry in
                            Button {
                                store.restore(entry)
                            } label: {
                                VStack(alignment: .trailing, spacing: 4) {
                                    Text(MathDisplayFormatting.expression(entry.expression))
                                        .font(.system(size: 11, weight: .medium, design: .rounded))
                                        .foregroundStyle(CalculatorPalette.secondaryText)
                                        .lineLimit(1)
                                        .truncationMode(.head)
                                    Text(entry.result)
                                        .font(.system(size: 16, weight: .medium, design: .rounded))
                                        .foregroundStyle(CalculatorPalette.primaryText)
                                        .monospacedDigit()
                                        .lineLimit(1)
                                }
                                .frame(maxWidth: .infinity, alignment: .trailing)
                                .padding(.horizontal, 11)
                                .frame(height: 57)
                                .background {
                                    RoundedRectangle(cornerRadius: 13, style: .continuous)
                                        .fill(CalculatorPalette.historyRow)
                                        .overlay {
                                            RoundedRectangle(cornerRadius: 13, style: .continuous)
                                                .strokeBorder(CalculatorPalette.border, lineWidth: 0.75)
                                        }
                                }
                                .contentShape(RoundedRectangle(cornerRadius: 13, style: .continuous))
                            }
                            .buttonStyle(.plain)
                            .accessibilityLabel("\(entry.expression) equals \(entry.result)")
                        }
                    }
                    .padding(12)
                }
            }
        }
        .frame(width: CalculatorLayout.historyWidth - 1, height: CalculatorLayout.windowHeight)
        .background(CalculatorPalette.historySurface)
    }
}
