import SwiftUI

struct MemoryRowView: View {
    @ObservedObject var store: CalculatorStore
    let keyWidth: CGFloat

    var body: some View {
        HStack(spacing: 6) {
            memoryButton("mc", label: "Memory clear", enabled: store.memory != nil, action: store.memoryClear)
            memoryButton("m+", label: "Memory add", action: store.memoryAdd)
            memoryButton("m−", label: "Memory subtract", action: store.memorySubtract)
            memoryButton("mr", label: "Memory recall", enabled: store.memory != nil, action: store.memoryRecall)
        }
    }

    private func memoryButton(
        _ title: String,
        label: String,
        enabled: Bool = true,
        action: @escaping () -> Void
    ) -> some View {
        CalculatorKeyButton(
            title: title,
            accessibilityLabel: label,
            tone: .scientific,
            width: keyWidth,
            isEnabled: enabled,
            action: action
        )
    }
}
