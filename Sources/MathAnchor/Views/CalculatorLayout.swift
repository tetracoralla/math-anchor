import SwiftUI

enum CalculatorLayout {
    static let basicWidth: CGFloat = 292
    // 6 columns of 59 pt + 5 gaps, one 8 pt seam, then the basic face's
    // 4 columns of 59 pt + 3 gaps, plus content insets: one aligned
    // ten-column face (6 × 59 + 5 × 8 + 8 + 4 × 59 + 3 × 8 + 2 × 16).
    static let scientificWidth: CGFloat = 694
    static let historyWidth: CGFloat = 248
    static let headerHeight: CGFloat = 44
    static let displayHeight: CGFloat = 124
    static let conversionDisplayHeight: CGFloat = 170
    static let conversionPanelHeight: CGFloat = 156
    static let displayKeypadSpacing: CGFloat = 12
    static let keyHeight: CGFloat = 52
    static let keySpacing: CGFloat = 8
    static let contentInset: CGFloat = 16
    // Leave the full keypad and its shadow above the rounded window mask.
    // CalculatorWindowConfigurator adds the live titlebar safe-area height to
    // these usable-content heights when it derives the NSWindow frame.
    static let keypadBottomInset: CGFloat = 20
    static let keypadHeight: CGFloat = keyHeight * 5 + keySpacing * 4
    static let windowHeight: CGFloat =
        headerHeight + displayHeight + displayKeypadSpacing + keypadHeight + keypadBottomInset
    static let conversionWindowHeight: CGFloat =
        headerHeight + conversionDisplayHeight + displayKeypadSpacing + keypadHeight + keypadBottomInset
    static let basicKeyWidth: CGFloat = 59
    static let conversionKeyWidth: CGFloat = 81.3333333333
    static let scientificKeyWidth: CGFloat = 59
    static let keyCornerRadius: CGFloat = 15
    static let compactKeyCornerRadius: CGFloat = 13
    static let modeTransitionDuration: TimeInterval = 0.2
}
