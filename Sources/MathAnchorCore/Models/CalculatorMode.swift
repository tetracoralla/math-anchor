import Foundation

package enum CalculatorMode: String, CaseIterable, Identifiable {
    case basic
    case scientific
    case conversion

    package var id: Self { self }

    package var title: String {
        switch self {
        case .basic: "Basic"
        case .scientific: "Scientific"
        case .conversion: "Convert"
        }
    }
}
