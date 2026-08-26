import AppKit
import SwiftUI
import MathAnchorCore

enum CalculatorPalette {
    static let canvasTop = dynamic(
        light: NSColor(srgbRed: 0.96, green: 0.97, blue: 0.98, alpha: 1),
        dark: NSColor(srgbRed: 0.075, green: 0.094, blue: 0.145, alpha: 1)
    )

    static let canvasBottom = dynamic(
        light: NSColor(srgbRed: 0.90, green: 0.92, blue: 0.95, alpha: 1),
        dark: NSColor(srgbRed: 0.045, green: 0.057, blue: 0.090, alpha: 1)
    )

    static let display = dynamic(
        light: NSColor(srgbRed: 1, green: 1, blue: 1, alpha: 0.80),
        dark: NSColor(srgbRed: 0.105, green: 0.133, blue: 0.200, alpha: 0.88)
    )

    static let digit = dynamic(
        light: NSColor(srgbRed: 0.99, green: 1, blue: 1, alpha: 0.86),
        dark: NSColor(srgbRed: 0.125, green: 0.157, blue: 0.220, alpha: 0.94)
    )

    static let action = dynamic(
        light: NSColor(srgbRed: 0.88, green: 0.90, blue: 0.94, alpha: 0.92),
        dark: NSColor(srgbRed: 0.175, green: 0.208, blue: 0.278, alpha: 0.96)
    )

    static let scientific = dynamic(
        light: NSColor(srgbRed: 0.93, green: 0.95, blue: 0.97, alpha: 0.78),
        dark: NSColor(srgbRed: 0.090, green: 0.116, blue: 0.170, alpha: 0.90)
    )

    static let operation = dynamic(
        light: NSColor(srgbRed: 0.86, green: 0.95, blue: 0.95, alpha: 0.94),
        dark: NSColor(srgbRed: 0.075, green: 0.180, blue: 0.196, alpha: 0.92)
    )

    static let commit = dynamic(
        light: NSColor(srgbRed: 0.055, green: 0.49, blue: 0.46, alpha: 1),
        dark: NSColor(srgbRed: 0.36, green: 0.86, blue: 0.80, alpha: 1)
    )

    static let accent = dynamic(
        light: NSColor(srgbRed: 0.03, green: 0.43, blue: 0.41, alpha: 1),
        dark: NSColor(srgbRed: 0.40, green: 0.91, blue: 0.85, alpha: 1)
    )

    static let accentInk = dynamic(
        light: NSColor(srgbRed: 0.96, green: 1, blue: 0.99, alpha: 1),
        dark: NSColor(srgbRed: 0.035, green: 0.13, blue: 0.13, alpha: 1)
    )

    static let control = dynamic(
        light: NSColor(srgbRed: 0.91, green: 0.93, blue: 0.96, alpha: 0.88),
        dark: NSColor(srgbRed: 0.115, green: 0.143, blue: 0.205, alpha: 0.88)
    )

    static let controlActive = dynamic(
        light: NSColor(srgbRed: 0.82, green: 0.93, blue: 0.92, alpha: 0.96),
        dark: NSColor(srgbRed: 0.090, green: 0.235, blue: 0.245, alpha: 0.96)
    )

    static let historySurface = dynamic(
        light: NSColor(srgbRed: 0.94, green: 0.95, blue: 0.97, alpha: 0.97),
        dark: NSColor(srgbRed: 0.060, green: 0.075, blue: 0.112, alpha: 0.98)
    )

    static let historyRow = dynamic(
        light: NSColor(srgbRed: 1, green: 1, blue: 1, alpha: 0.66),
        dark: NSColor(srgbRed: 0.105, green: 0.130, blue: 0.185, alpha: 0.72)
    )

    static let border = dynamic(
        light: NSColor(srgbRed: 0.16, green: 0.22, blue: 0.31, alpha: 0.12),
        dark: NSColor(srgbRed: 0.82, green: 0.90, blue: 1, alpha: 0.12)
    )

    static let strongBorder = dynamic(
        light: NSColor(srgbRed: 0.05, green: 0.42, blue: 0.40, alpha: 0.28),
        dark: NSColor(srgbRed: 0.42, green: 0.91, blue: 0.85, alpha: 0.30)
    )

    static let primaryText = dynamic(
        light: NSColor(srgbRed: 0.08, green: 0.11, blue: 0.17, alpha: 1),
        dark: NSColor(srgbRed: 0.94, green: 0.97, blue: 1, alpha: 1)
    )

    static let secondaryText = dynamic(
        light: NSColor(srgbRed: 0.25, green: 0.31, blue: 0.40, alpha: 0.78),
        dark: NSColor(srgbRed: 0.74, green: 0.80, blue: 0.89, alpha: 0.76)
    )

    static let error = dynamic(
        light: NSColor(srgbRed: 0.73, green: 0.15, blue: 0.20, alpha: 1),
        dark: NSColor(srgbRed: 1, green: 0.45, blue: 0.49, alpha: 1)
    )

    static let warning = dynamic(
        light: NSColor(srgbRed: 0.63, green: 0.38, blue: 0.04, alpha: 1),
        dark: NSColor(srgbRed: 1.00, green: 0.72, blue: 0.32, alpha: 1)
    )

    private static func dynamic(light: NSColor, dark: NSColor) -> Color {
        Color(nsColor: NSColor(name: nil) { appearance in
            appearance.bestMatch(from: [.darkAqua, .aqua]) == .darkAqua ? dark : light
        })
    }
}
