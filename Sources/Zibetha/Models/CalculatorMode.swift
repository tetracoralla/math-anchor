import Foundation

enum CalculatorMode: String, CaseIterable, Identifiable {
    case basic
    case scientific
    case conversion

    var id: Self { self }

    var title: String {
        switch self {
        case .basic: "Basic"
        case .scientific: "Scientific"
        case .conversion: "Convert"
        }
    }

    var systemImage: String {
        switch self {
        case .basic: "plus.forwardslash.minus"
        case .scientific: "function"
        case .conversion: "ruler"
        }
    }
}
