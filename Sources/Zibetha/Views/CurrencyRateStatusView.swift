import SwiftUI

struct CurrencyRateStatusView: View {
    @ObservedObject var store: UnitConversionStore

    var body: some View {
        TimelineView(.periodic(from: .now, by: 60)) { context in
            Button {
                store.setPopover(.rateDetails, presented: true)
            } label: {
                HStack(spacing: 4) {
                    Text("ECB")
                        .fontWeight(.semibold)

                    if store.rateMetadata != nil {
                        Text("·")

                        Text(summaryTime)
                            .lineLimit(1)
                    }

                    Spacer(minLength: 3)

                    statusLabel(at: context.date)
                }
                .font(.system(size: 9.5, weight: .medium, design: .rounded))
                .foregroundStyle(CalculatorPalette.secondaryText)
                .frame(maxWidth: .infinity, minHeight: 16)
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .accessibilityLabel(accessibilitySummary(at: context.date))
        }
        .popover(isPresented: ratePopoverBinding, arrowEdge: .bottom) {
            detailPopover
        }
    }

    @ViewBuilder
    private func statusLabel(at date: Date) -> some View {
        let status = status(at: date)
        Text(status.title)
            .font(.system(size: 8.5, weight: .bold, design: .rounded))
            .foregroundStyle(status.color)
            .padding(.horizontal, 5)
            .frame(height: 15)
            .background {
                Capsule().fill(status.color.opacity(0.12))
            }
    }

    private var detailPopover: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(alignment: .firstTextBaseline) {
                Text("Reference rate")
                    .font(.system(size: 13, weight: .semibold, design: .rounded))
                Spacer()
                statusLabel(at: .now)
            }

            if let metadata = store.rateMetadata {
                Link(metadata.sourceName, destination: metadata.sourceURL)
                    .font(.system(size: 12, weight: .medium, design: .rounded))

                VStack(spacing: 6) {
                    detailRow("Published", publishedText(metadata))
                    detailRow("Checked", Self.dateTime.string(from: metadata.checkedAt))
                    detailRow("Expires", Self.dateTime.string(from: metadata.expiresAt))
                    if let nextRefreshAttemptAt = metadata.nextRefreshAttemptAt,
                       metadata.refreshDeferred || metadata.refreshFailed {
                        detailRow("Retry after", Self.dateTime.string(from: nextRefreshAttemptAt))
                    }
                }

                if let rateMessage = store.rateMessage {
                    Text(rateMessage)
                        .font(.system(size: 10, weight: .semibold, design: .rounded))
                        .foregroundStyle(CalculatorPalette.warning)
                }
            } else {
                Text("European Central Bank")
                    .font(.system(size: 12, weight: .medium, design: .rounded))
                Text("No rate data is available.")
                    .font(.system(size: 10, design: .rounded))
                    .foregroundStyle(CalculatorPalette.secondaryText)
            }

            Text("Calculated from ECB euro reference rates. For information only — not a transaction quote.")
                .font(.system(size: 10, design: .rounded))
                .foregroundStyle(CalculatorPalette.secondaryText)
                .fixedSize(horizontal: false, vertical: true)

            Button(store.isConverting ? "Updating…" : "Refresh rates") {
                store.refreshRates()
            }
            .buttonStyle(.bordered)
            .controlSize(.small)
            .disabled(store.isConverting)
        }
        .padding(12)
        .frame(width: 256)
        .background(CalculatorPalette.historySurface)
    }

    private func detailRow(_ label: String, _ value: String) -> some View {
        HStack(alignment: .firstTextBaseline, spacing: 8) {
            Text(label)
                .foregroundStyle(CalculatorPalette.secondaryText)
            Spacer()
            Text(value)
                .foregroundStyle(CalculatorPalette.primaryText)
        }
        .font(.system(size: 10, weight: .medium, design: .rounded))
    }

    private var summaryTime: String {
        guard let metadata = store.rateMetadata else {
            return store.isConverting ? "Updating rates" : "Rates unavailable"
        }
        if let publishedAt = metadata.publishedAt {
            return Self.compactDateTime.string(from: publishedAt)
        }
        return metadata.rateDate
    }

    private func publishedText(_ metadata: CurrencyRateMetadata) -> String {
        if let publishedAt = metadata.publishedAt {
            return Self.dateTime.string(from: publishedAt)
        }
        return metadata.rateDate
    }

    private func status(at date: Date) -> (title: String, color: Color) {
        if store.errorMessage != nil {
            return ("UNAVAILABLE", CalculatorPalette.error)
        }
        if store.isConverting && store.rateMetadata == nil {
            return ("UPDATING", CalculatorPalette.accent)
        }
        guard let metadata = store.rateMetadata else {
            return ("UNAVAILABLE", CalculatorPalette.error)
        }
        if metadata.isExpired(at: date) {
            return ("EXPIRED", CalculatorPalette.warning)
        }
        if store.isConverting {
            return ("UPDATING", CalculatorPalette.accent)
        }
        return ("CURRENT", CalculatorPalette.accent)
    }

    private var ratePopoverBinding: Binding<Bool> {
        Binding(
            get: { store.activePopover == .rateDetails },
            set: { store.setPopover(.rateDetails, presented: $0) }
        )
    }

    private func accessibilitySummary(at date: Date) -> String {
        let state = status(at: date).title.lowercased()
        return "ECB reference rate, \(summaryTime), \(state)"
    }

    private static let compactDateTime: DateFormatter = {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.dateFormat = "MMM d, HH:mm"
        return formatter
    }()

    private static let dateTime: DateFormatter = {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.dateStyle = .medium
        formatter.timeStyle = .short
        return formatter
    }()
}
