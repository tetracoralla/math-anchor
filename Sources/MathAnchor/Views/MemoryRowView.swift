import SwiftUI

struct MemoryRowView: View {
    @ObservedObject var store: CalculatorStore
    let keyWidth: CGFloat

    var body: some View {
        HStack(spacing: 6) {
            memoryButton("mc", enabled: store.memory != nil, action: store.memoryClear)
            memoryButton("m+", action: store.memoryAdd)
            memoryButton("m−", action: store.memorySubtract)
            memoryButton("mr", enabled: store.memory != nil, action: store.memoryRecall)
        }
    }

    private func memoryButton(
        _ title: String,
        enabled: Bool = true,
        action: @escaping () -> Void
    ) -> some View {
        CalculatorKeyButton(
            title: title,
            accessibilityLabel: title,
            tone: .scientific,
            width: keyWidth,
            isEnabled: enabled,
            action: action
        )
    }
}
