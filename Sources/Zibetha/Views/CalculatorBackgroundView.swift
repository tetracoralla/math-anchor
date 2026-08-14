import SwiftUI

struct CalculatorBackgroundView: View {
    var body: some View {
        ZStack {
            LinearGradient(
                colors: [CalculatorPalette.canvasTop, CalculatorPalette.canvasBottom],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )

            RadialGradient(
                colors: [CalculatorPalette.accent.opacity(0.12), .clear],
                center: .topTrailing,
                startRadius: 0,
                endRadius: 290
            )
        }
        .ignoresSafeArea()
    }
}
