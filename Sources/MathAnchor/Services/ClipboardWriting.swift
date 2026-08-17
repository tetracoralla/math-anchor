import AppKit

@MainActor
protocol ClipboardWriting {
    func write(_ value: String)
}

struct SystemClipboard: ClipboardWriting {
    func write(_ value: String) {
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(value, forType: .string)
    }
}
