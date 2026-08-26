import SwiftUI

struct ContentView: View {
    @ObservedObject var store: CalculatorStore
    @ObservedObject var conversionStore: UnitConversionStore
    let modeTransition: CalculatorModeTransition
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    private var calculatorWidth: CGFloat {
        store.mode == .scientific ? CalculatorLayout.scientificWidth : CalculatorLayout.basicWidth
    }

    private var totalWidth: CGFloat {
        calculatorWidth + (store.isHistoryPresented ? CalculatorLayout.historyWidth : 0)
    }

    private var calculatorHeight: CGFloat {
        store.mode == .conversion
            ? CalculatorLayout.conversionWindowHeight
            : CalculatorLayout.windowHeight
    }

    var body: some View {
        ZStack {
            CalculatorBackgroundView()

            HStack(spacing: 0) {
                VStack(spacing: 0) {
                    CalculatorHeaderView(
                        store: store,
                        onToggleModeMenu: {
                            modeTransition.toggleModeMenu(
                                calculatorStore: store,
                                conversionStore: conversionStore
                            )
                        },
                        onSelectMode: { mode in
                            modeTransition.select(
                                mode,
                                calculatorStore: store,
                                conversionStore: conversionStore
                            )
                        }
                    )
                    if store.mode == .conversion {
                        ConversionDisplayView(store: conversionStore)
                    } else {
                        DisplayView(store: store)
                    }

                    Spacer()
                        .frame(height: CalculatorLayout.displayKeypadSpacing)

                    if store.mode == .conversion {
                        ConversionKeypadView(store: conversionStore)
                            .equatable()
                            .padding(.horizontal, CalculatorLayout.contentInset)
                            .padding(.bottom, CalculatorLayout.keypadBottomInset)
                    } else {
                        HStack(alignment: .bottom, spacing: CalculatorLayout.keySpacing) {
                            if store.mode == .scientific {
                                ScientificKeypadView(store: store)
                                    .equatable()
                                    .transition(.opacity)
                            }
                            BasicKeypadView(store: store)
                                .equatable()
                        }
                        .padding(.horizontal, CalculatorLayout.contentInset)
                        .padding(.bottom, CalculatorLayout.keypadBottomInset)
                    }
                }
                .frame(width: calculatorWidth, height: calculatorHeight)
                .animation(
                    reduceMotion
                        ? nil
                        : .easeInOut(duration: CalculatorLayout.modeTransitionDuration),
                    value: store.mode
                )

                if store.isHistoryPresented {
                    Rectangle()
                        .fill(CalculatorPalette.border)
                        .frame(width: 1)
                        .transition(.opacity)

                    HistoryView(store: store)
                        .transition(.move(edge: .trailing).combined(with: .opacity))
                }
            }
            .animation(
                reduceMotion
                    ? nil
                    : .easeInOut(duration: CalculatorLayout.modeTransitionDuration),
                value: store.isHistoryPresented
            )
        }
        .frame(width: totalWidth, height: calculatorHeight)
        .background(
            CalculatorWindowConfigurator(
                contentSize: CGSize(
                    width: totalWidth,
                    height: calculatorHeight
                )
            )
        )
        .calculatorKeyboard(store, conversionStore: conversionStore)
    }
}
