import SwiftUI

enum CalculatorButtonTone {
    case digit
    case action
    case operation
    case commit
    case scientific
}

struct CalculatorKeyButton: View {
    let title: String
    var systemImage: String? = nil
    var accessibilityLabel: String? = nil
    var tone: CalculatorButtonTone = .digit
    var shortcut: KeyEquivalent? = nil
    var width: CGFloat
    var height: CGFloat = CalculatorLayout.keyHeight
    var symbolSize: CGFloat? = nil
    var symbolYOffset: CGFloat = 0
    var textSize: CGFloat? = nil
    var textYOffset: CGFloat = 0
    var isEnabled = true
    let action: () -> Void

    var body: some View {
        shortcutButton
    }

    @ViewBuilder
    private var shortcutButton: some View {
        if let shortcut {
            button.keyboardShortcut(shortcut, modifiers: [])
        } else {
            button
        }
    }

    private var button: some View {
        Button(action: action) {
            Group {
                if let systemImage {
                    Image(systemName: systemImage)
                        .font(.system(size: symbolSize ?? 19, weight: .medium))
                        .symbolRenderingMode(.monochrome)
                        .frame(width: 26, height: 26)
                        .offset(y: symbolYOffset)
                } else {
                    Text(title)
                        .font(keyFont)
                        .monospacedDigit()
                        .offset(y: textYOffset)
                }
            }
            .frame(width: width, height: height)
            .contentShape(
                RoundedRectangle(
                    cornerRadius: cornerRadius,
                    style: .continuous
                )
            )
        }
        .buttonStyle(CalculatorKeyStyle(tone: tone))
        .disabled(!isEnabled)
        .opacity(isEnabled ? 1 : 0.34)
        .accessibilityLabel(accessibilityLabel ?? title)
    }

    private var keyFont: Font {
        let size = textSize ?? (tone == .scientific ? 13 : 22)
        let weight: Font.Weight = tone == .digit ? .medium : .semibold
        return .system(size: size, weight: weight, design: .rounded)
    }

    private var cornerRadius: CGFloat {
        tone == .scientific
            ? CalculatorLayout.compactKeyCornerRadius
            : CalculatorLayout.keyCornerRadius
    }
}

private struct CalculatorKeyStyle: ButtonStyle {
    let tone: CalculatorButtonTone

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .foregroundStyle(foreground)
            .background {
                RoundedRectangle(cornerRadius: cornerRadius, style: .continuous)
                    .fill(background)
            }
            .overlay {
                RoundedRectangle(cornerRadius: cornerRadius, style: .continuous)
                    .strokeBorder(border, lineWidth: tone == .operation ? 1 : 0.75)
            }
            .shadow(color: .black.opacity(tone == .commit ? 0.18 : 0.12), radius: 1.6, y: 1)
            .brightness(configuration.isPressed ? -0.065 : 0)
            .offset(y: configuration.isPressed ? 1 : 0)
            .animation(.easeOut(duration: 0.07), value: configuration.isPressed)
    }

    private var background: Color {
        switch tone {
        case .digit: CalculatorPalette.digit
        case .action: CalculatorPalette.action
        case .operation: CalculatorPalette.operation
        case .commit: CalculatorPalette.commit
        case .scientific: CalculatorPalette.scientific
        }
    }

    private var foreground: Color {
        switch tone {
        case .operation: CalculatorPalette.accent
        case .commit: CalculatorPalette.accentInk
        default: CalculatorPalette.primaryText
        }
    }

    private var border: Color {
        switch tone {
        case .operation: CalculatorPalette.strongBorder
        case .commit: CalculatorPalette.commit.opacity(0.70)
        default: CalculatorPalette.border
        }
    }

    private var cornerRadius: CGFloat {
        tone == .scientific
            ? CalculatorLayout.compactKeyCornerRadius
            : CalculatorLayout.keyCornerRadius
    }
}
