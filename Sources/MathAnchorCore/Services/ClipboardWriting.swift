import AppKit

@MainActor
package protocol ClipboardWriting {
    func write(_ value: String)
}

package struct SystemClipboard: ClipboardWriting {
    package func write(_ value: String) {
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(value, forType: .string)
    }
}
