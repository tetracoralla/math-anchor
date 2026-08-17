import SwiftUI

struct CalculatorHeaderView: View {
    @ObservedObject var store: CalculatorStore

    var body: some View {
        HStack(spacing: 9) {
            Spacer()

            if store.mode != .conversion {
                Button {
                    store.isHistoryPresented.toggle()
                } label: {
                    headerControl(
                        systemName: "clock.arrow.circlepath",
                        iconSize: 13.5,
                        isActive: store.isHistoryPresented
                    )
                }
                .buttonStyle(.plain)
                .help("History")
                .accessibilityLabel("History")
            }

            modeMenu
        }
        .padding(.horizontal, CalculatorLayout.contentInset)
        .frame(height: CalculatorLayout.headerHeight, alignment: .center)
    }

    private func controlSurface<Content: View>(
        isActive: Bool,
        @ViewBuilder content: () -> Content
    ) -> some View {
        ZStack {
            RoundedRectangle(cornerRadius: 9, style: .continuous)
                .fill(isActive ? CalculatorPalette.controlActive : CalculatorPalette.control)
            RoundedRectangle(cornerRadius: 9, style: .continuous)
                .strokeBorder(
                    isActive ? CalculatorPalette.strongBorder : CalculatorPalette.border,
                    lineWidth: 0.75
                )
            content()
        }
        .frame(width: 32, height: 28)
        .contentShape(RoundedRectangle(cornerRadius: 9, style: .continuous))
    }

    private func headerControl(
        systemName: String,
        iconSize: CGFloat,
        yOffset: CGFloat = 0,
        isActive: Bool = false
    ) -> some View {
        controlSurface(isActive: isActive) {
            Image(systemName: systemName)
                .font(.system(size: iconSize, weight: .semibold))
                .symbolRenderingMode(.monochrome)
                .foregroundStyle(isActive ? CalculatorPalette.accent : CalculatorPalette.primaryText)
                .frame(width: 18, height: 18)
                .offset(y: yOffset)
        }
    }

    private var modeMenu: some View {
        Button {
            store.isModePopoverPresented.toggle()
        } label: {
            modeHeaderControl
        }
        .buttonStyle(.plain)
        .help("Calculator mode")
        .accessibilityLabel("Calculator mode")
        .popover(isPresented: $store.isModePopoverPresented, arrowEdge: .top) {
            modePopover
        }
    }

    private var modeHeaderControl: some View {
        controlSurface(isActive: store.isModePopoverPresented) {
            CalculatorModeIcon(
                mode: store.mode,
                size: store.mode == .scientific ? 16.5 : 14.5
            )
            .foregroundStyle(
                store.isModePopoverPresented ? CalculatorPalette.accent : CalculatorPalette.primaryText
            )
            .offset(y: store.mode == .scientific ? 0.25 : 0)
        }
    }

    private var modePopover: some View {
        VStack(spacing: 4) {
            ForEach(CalculatorMode.allCases) { mode in
                Button {
                    store.selectMode(mode)
                } label: {
                    HStack(spacing: 10) {
                        CalculatorModeIcon(mode: mode, size: 12)
                            .frame(width: 16)
                        Text(mode.title)
                        Spacer()
                        if store.mode == mode {
                            Image(systemName: "checkmark")
                                .font(.system(size: 11, weight: .semibold))
                        }
                    }
                    .foregroundStyle(store.mode == mode ? CalculatorPalette.accent : CalculatorPalette.primaryText)
                    .padding(.horizontal, 9)
                    .frame(height: 30)
                    .background {
                        RoundedRectangle(cornerRadius: 8, style: .continuous)
                            .fill(store.mode == mode ? CalculatorPalette.controlActive : .clear)
                    }
                    .contentShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
                }
                .buttonStyle(.plain)
            }

            if store.mode != .conversion {
                Divider()
                    .padding(.vertical, 3)

                Button {
                    store.isHistoryPresented.toggle()
                    store.isModePopoverPresented = false
                } label: {
                    Text(store.isHistoryPresented ? "Hide History" : "Show History")
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding(.horizontal, 9)
                        .frame(height: 30)
                        .contentShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
                }
                .buttonStyle(.plain)
            }
        }
        .font(.system(size: 13, weight: .regular))
        .padding(7)
        .frame(width: 164)
    }
}
