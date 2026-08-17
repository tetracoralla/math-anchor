import SwiftUI

struct ContentView: View {
    @ObservedObject var store: CalculatorStore
    @ObservedObject var conversionStore: UnitConversionStore

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
                    CalculatorHeaderView(store: store)
                    if store.mode == .conversion {
                        ConversionDisplayView(store: conversionStore)
                    } else {
                        DisplayView(store: store)
                    }

                    Spacer()
                        .frame(height: CalculatorLayout.displayKeypadSpacing)

                    if store.mode == .conversion {
                        ConversionKeypadView(store: conversionStore)
                            .padding(.horizontal, CalculatorLayout.contentInset)
                            .padding(.bottom, 14)
                    } else {
                        HStack(alignment: .bottom, spacing: 12) {
                            if store.mode == .scientific {
                                ScientificKeypadView(store: store)
                            }
                            BasicKeypadView(store: store)
                        }
                        .padding(.horizontal, CalculatorLayout.contentInset)
                        .padding(.bottom, 14)
                    }
                }
                .frame(width: calculatorWidth, height: calculatorHeight)

                if store.isHistoryPresented {
                    Rectangle()
                        .fill(CalculatorPalette.border)
                        .frame(width: 1)
                    HistoryView(store: store)
                }
            }
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
        .onChange(of: store.mode) { _, mode in
            conversionStore.dismissActivePopover()
            if mode == .conversion {
                conversionStore.activate()
            }
        }
    }
}
