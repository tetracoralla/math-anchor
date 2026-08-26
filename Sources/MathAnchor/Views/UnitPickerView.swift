import SwiftUI
import MathAnchorCore

struct UnitPickerView: View {
    let selection: UnitDefinition
    let units: [UnitDefinition]
    var pickerAccessibilityLabel = "Unit"
    @Binding var isPresented: Bool
    let onSelect: (UnitDefinition) -> Void

    @State private var query = ""
    @FocusState private var searchFocused: Bool

    private var filteredUnits: [UnitDefinition] {
        let search = query.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !search.isEmpty else { return units }
        return units.filter {
            $0.name.localizedCaseInsensitiveContains(search)
                || $0.symbol.localizedCaseInsensitiveContains(search)
                || $0.category.title.localizedCaseInsensitiveContains(search)
        }
    }

    var body: some View {
        Button {
            isPresented = true
        } label: {
            HStack(spacing: 5) {
                Text(selection.symbol)
                    .lineLimit(1)
                Image(systemName: "chevron.down")
                    .font(.system(size: 8, weight: .bold))
            }
            .font(.system(size: 12, weight: .semibold, design: .rounded))
            .foregroundStyle(CalculatorPalette.primaryText)
            .padding(.horizontal, 8)
            .frame(height: 24)
            .background {
                Capsule()
                    .fill(CalculatorPalette.control)
                    .overlay {
                        Capsule().strokeBorder(CalculatorPalette.border, lineWidth: 0.75)
                    }
            }
            .contentShape(Capsule())
        }
        .buttonStyle(.plain)
        .help(selection.name)
        .accessibilityLabel(pickerAccessibilityLabel)
        .accessibilityValue(selection.name)
        .popover(isPresented: $isPresented, arrowEdge: .top) {
            pickerContent
        }
        .onChange(of: isPresented) { _, presented in
            if !presented {
                query = ""
            }
        }
    }

    private var pickerContent: some View {
        VStack(spacing: 8) {
            TextField("Search units", text: $query)
                .textFieldStyle(.roundedBorder)
                .focused($searchFocused)
                .accessibilityLabel("Search units")
                .onAppear {
                    searchFocused = true
                }

            ScrollView {
                LazyVStack(alignment: .leading, spacing: 3) {
                    ForEach(UnitCategory.allCases) { category in
                        let categoryUnits = filteredUnits.filter { $0.category == category }
                        if !categoryUnits.isEmpty {
                            Text(category.title.uppercased())
                                .font(.system(size: 9, weight: .bold, design: .rounded))
                                .foregroundStyle(CalculatorPalette.secondaryText)
                                .padding(.horizontal, 7)
                                .padding(.top, 5)

                            ForEach(categoryUnits) { unit in
                                Button {
                                    onSelect(unit)
                                    query = ""
                                    isPresented = false
                                } label: {
                                    HStack(spacing: 8) {
                                        Text(unit.name)
                                            .lineLimit(1)
                                        Spacer()
                                        Text(unit.symbol)
                                            .foregroundStyle(CalculatorPalette.secondaryText)
                                        if unit == selection {
                                            Image(systemName: "checkmark")
                                                .font(.system(size: 10, weight: .semibold))
                                                .foregroundStyle(CalculatorPalette.accent)
                                        }
                                    }
                                    .font(.system(size: 12, design: .rounded))
                                    .foregroundStyle(CalculatorPalette.primaryText)
                                    .padding(.horizontal, 7)
                                    .frame(height: 28)
                                    .background {
                                        RoundedRectangle(cornerRadius: 7, style: .continuous)
                                            .fill(unit == selection ? CalculatorPalette.controlActive : .clear)
                                    }
                                    .contentShape(Rectangle())
                                }
                                .buttonStyle(.plain)
                            }
                        }
                    }

                    if filteredUnits.isEmpty {
                        Text("No matching units")
                            .font(.system(size: 12, design: .rounded))
                            .foregroundStyle(CalculatorPalette.secondaryText)
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 22)
                    }
                }
            }
        }
        .padding(10)
        .frame(width: 250, height: 310)
        .background(CalculatorPalette.historySurface)
    }
}
