import SwiftUI

struct InlineErrorView: View {
    let message: String
    var fontSize: CGFloat = 10

    var body: some View {
        Text(message)
            .font(.system(size: fontSize, weight: .semibold, design: .rounded))
            .foregroundStyle(CalculatorPalette.error)
            .multilineTextAlignment(.trailing)
            .lineLimit(2)
            .minimumScaleFactor(0.85)
            .frame(maxWidth: .infinity, alignment: .trailing)
            .layoutPriority(1)
            .help(message)
            .accessibilityElement(children: .ignore)
            .accessibilityLabel("Error")
            .accessibilityValue(message)
    }
}
