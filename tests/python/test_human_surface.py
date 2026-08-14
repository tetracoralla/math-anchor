from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_display_is_a_calculator_surface_not_a_text_editor() -> None:
    display = (ROOT / "Sources/Zibetha/Views/DisplayView.swift").read_text()
    views = "\n".join(
        path.read_text() for path in (ROOT / "Sources/Zibetha/Views").glob("*.swift")
    )

    assert "TextField(" not in display
    assert "@FocusState" not in display
    assert "replaceExpression(" not in views


def test_exact_value_stays_off_the_default_human_surface() -> None:
    display = (ROOT / "Sources/Zibetha/Views/DisplayView.swift").read_text()
    history = (ROOT / "Sources/Zibetha/Views/HistoryView.swift").read_text()

    assert 'Text("Exact")' not in display
    assert 'Text("Exact")' not in history
    assert 'Button("Copy Exact Value"' in display


def test_application_name_stays_off_the_human_surface() -> None:
    app = (ROOT / "Sources/Zibetha/App/ZibethaApp.swift").read_text()
    views = "\n".join(
        path.read_text() for path in (ROOT / "Sources/Zibetha/Views").glob("*.swift")
    )

    assert 'WindowGroup("Calculator")' in app
    assert 'WindowGroup("Zibetha")' not in app
    assert "Zibetha" not in views
    assert 'Text("EXACT")' not in views


def test_header_has_no_visible_brand_mark() -> None:
    header = (ROOT / "Sources/Zibetha/Views/CalculatorHeaderView.swift").read_text()

    assert "CalculatorBrandMark" not in header
    assert not (ROOT / "Sources/Zibetha/Views/CalculatorBrandMark.swift").exists()


def test_expression_is_secondary_only_after_evaluation() -> None:
    display = (ROOT / "Sources/Zibetha/Views/DisplayView.swift").read_text()

    assert "if store.isShowingResult" in display
    assert 'accessibilityLabel(store.isShowingResult ? "Result" : "Expression")' in display


def test_mode_menu_uses_the_visible_rounded_rectangle_as_its_trigger() -> None:
    header = (ROOT / "Sources/Zibetha/Views/CalculatorHeaderView.swift").read_text()
    keyboard = (
        ROOT / "Sources/Zibetha/Support/CalculatorKeyboardMonitor.swift"
    ).read_text()

    assert "Color.clear" not in header
    assert "Menu {" not in header
    assert ".popover(isPresented:" in header
    assert ".contentShape(RoundedRectangle(cornerRadius: 9, style: .continuous))" in header
    assert ".contentShape(Circle())" not in header
    assert "if store.isModePopoverPresented" in keyboard


def test_conversion_is_a_lightweight_numeric_mode() -> None:
    mode = (ROOT / "Sources/Zibetha/Models/CalculatorMode.swift").read_text()
    content = (ROOT / "Sources/Zibetha/Views/ContentView.swift").read_text()
    display = (ROOT / "Sources/Zibetha/Views/ConversionDisplayView.swift").read_text()
    keypad = (ROOT / "Sources/Zibetha/Views/ConversionKeypadView.swift").read_text()
    picker = (ROOT / "Sources/Zibetha/Views/UnitPickerView.swift").read_text()

    assert "case conversion" in mode
    assert "ConversionDisplayView" in content
    assert "ConversionKeypadView" in content
    assert "TextField(" not in display
    assert 'TextField("Search units"' in picker
    assert ".background(CalculatorPalette.historySurface)" in picker
    assert "store.appendDigit" in keypad
    assert 'accessibilityLabel: "Swap units"' in keypad
    assert 'case .conversion: "ruler"' in mode
    assert 'case .conversion: "arrow.left.arrow.right"' not in mode
    assert 'systemImage: "equal"' not in keypad
    assert "private func valueRow" in display
    assert 'Image(systemName: "arrow.down")' in display
    assert 'Image(systemName: "arrow.right")' not in display


def test_conversion_keeps_currency_status_human_facing_and_agent_catalog_unchanged() -> None:
    runtime = (ROOT / "Sources/Zibetha/Services/MathRuntimeService.swift").read_text()
    status = (ROOT / "Sources/Zibetha/Views/CurrencyRateStatusView.swift").read_text()
    registry = (ROOT / "src/zibetha/catalog.py").read_text()

    assert 'operation: "units.convert"' in runtime
    assert 'operation: "currency.convert"' in runtime
    assert 'Text("ECB")' in status
    assert 'detailRow("Published"' in status
    assert 'detailRow("Checked"' in status
    assert 'detailRow("Expires"' in status
    assert 'return ("EXPIRED"' in status
    assert "not a transaction quote" in status
    assert 'id="currency.convert"' not in registry


def test_conversion_popovers_and_text_editing_own_keyboard_focus() -> None:
    keyboard = (
        ROOT / "Sources/Zibetha/Support/CalculatorKeyboardMonitor.swift"
    ).read_text()
    content = (ROOT / "Sources/Zibetha/Views/ContentView.swift").read_text()

    assert "shouldDeferToFocusedTextInput" in keyboard
    assert "conversionStore.dismissActivePopover()" in keyboard
    assert "conversionStore.dismissActivePopover()" in content
