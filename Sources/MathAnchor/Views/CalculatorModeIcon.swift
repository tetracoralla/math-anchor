import SwiftUI
import MathAnchorCore

struct CalculatorModeIcon: View {
    let mode: CalculatorMode
    let size: CGFloat

    var body: some View {
        Group {
            switch mode {
            case .conversion:
                simplifiedRuler
            case .basic:
                symbol("plus.forwardslash.minus")
            case .scientific:
                symbol("function")
            }
        }
        .frame(width: 18, height: 18)
    }

    private func symbol(_ name: String) -> some View {
        Image(systemName: name)
            .font(.system(size: size, weight: .semibold))
            .symbolRenderingMode(.monochrome)
    }

    private var simplifiedRuler: some View {
        ZStack(alignment: .top) {
            RoundedRectangle(cornerRadius: 2.5, style: .continuous)
                .strokeBorder(lineWidth: 1.35)
                .frame(width: size + 2.5, height: size * 0.68)

            HStack(alignment: .top, spacing: 2.4) {
                tick(height: size * 0.22)
                tick(height: size * 0.34)
                tick(height: size * 0.22)
            }
            .padding(.top, 1.5)
        }
        .frame(width: size + 2.5, height: size * 0.68)
    }

    private func tick(height: CGFloat) -> some View {
        Capsule()
            .frame(width: 1.2, height: height)
    }
}
