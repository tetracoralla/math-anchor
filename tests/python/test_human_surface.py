from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_display_is_a_calculator_surface_not_a_text_editor() -> None:
    display = (ROOT / "Sources/MathAnchor/Views/DisplayView.swift").read_text()
    views = "\n".join(
        path.read_text() for path in (ROOT / "Sources/MathAnchor/Views").glob("*.swift")
    )

    assert "TextField(" not in display
    assert "@FocusState" not in display
    assert "replaceExpression(" not in views


def test_exact_value_stays_off_the_default_human_surface() -> None:
    display = (ROOT / "Sources/MathAnchor/Views/DisplayView.swift").read_text()
    history = (ROOT / "Sources/MathAnchor/Views/HistoryView.swift").read_text()

    assert 'Text("Exact")' not in display
    assert 'Text("Exact")' not in history
    assert 'Button("Copy Exact Value"' in display


def test_application_name_stays_off_the_human_surface() -> None:
    app = (ROOT / "Sources/MathAnchor/App/MathAnchorApp.swift").read_text()
    views = "\n".join(
        path.read_text() for path in (ROOT / "Sources/MathAnchor/Views").glob("*.swift")
    )

    assert 'WindowGroup("Calculator")' in app
    assert 'WindowGroup("Math Anchor")' not in app
    assert "Math Anchor" not in views
    assert 'Text("EXACT")' not in views


def test_header_has_no_visible_brand_mark() -> None:
    header = (ROOT / "Sources/MathAnchor/Views/CalculatorHeaderView.swift").read_text()

    assert "CalculatorBrandMark" not in header
    assert not (ROOT / "Sources/MathAnchor/Views/CalculatorBrandMark.swift").exists()


def test_expression_is_secondary_only_after_evaluation() -> None:
    display = (ROOT / "Sources/MathAnchor/Views/DisplayView.swift").read_text()

    assert "if store.isShowingResult" in display
    assert 'accessibilityLabel(store.isShowingResult ? "Result" : "Expression")' in display
    # The visual secondary expression is intentionally folded into the
    # primary Result value. This avoids SwiftUI's accidental Expression-only
    # flattening while keeping one concise VoiceOver focus stop.
    assert ".accessibilityHidden(true)" in display
    assert '"\\(store.expressionForDisplay) equals \\(store.display)"' in display
    assert ".accessibilityValue(displayAccessibilityValue)" in display


def test_mode_menu_uses_the_visible_rounded_rectangle_as_its_trigger() -> None:
    header = (ROOT / "Sources/MathAnchor/Views/CalculatorHeaderView.swift").read_text()
    keyboard = (
        ROOT / "Sources/MathAnchor/Support/CalculatorKeyboardMonitor.swift"
    ).read_text()

    assert "Color.clear" not in header
    assert "Menu {" not in header
    assert ".popover(isPresented:" in header
    assert ".contentShape(RoundedRectangle(cornerRadius: 9, style: .continuous))" in header
    assert ".contentShape(Circle())" not in header
    assert "if store.isModePopoverPresented" in keyboard


def test_conversion_is_a_lightweight_numeric_mode() -> None:
    mode = (ROOT / "Sources/MathAnchorCore/Models/CalculatorMode.swift").read_text()
    icon = (ROOT / "Sources/MathAnchor/Views/CalculatorModeIcon.swift").read_text()
    content = (ROOT / "Sources/MathAnchor/Views/ContentView.swift").read_text()
    display = (ROOT / "Sources/MathAnchor/Views/ConversionDisplayView.swift").read_text()
    keypad = (ROOT / "Sources/MathAnchor/Views/ConversionKeypadView.swift").read_text()
    picker = (ROOT / "Sources/MathAnchor/Views/UnitPickerView.swift").read_text()

    assert "case conversion" in mode
    assert "ConversionDisplayView" in content
    assert "ConversionKeypadView" in content
    assert "TextField(" not in display
    assert 'TextField("Search units"' in picker
    assert ".background(CalculatorPalette.historySurface)" in picker
    assert "store.appendDigit" in keypad
    assert 'accessibilityLabel: "Swap units"' in keypad
    assert "case .conversion:\n                simplifiedRuler" in icon
    assert "arrow.left.arrow.right" not in icon
    assert 'systemImage: "equal"' not in keypad
    assert "private func valueRow" in display
    assert 'Image(systemName: "arrow.down")' in display
    assert 'Image(systemName: "arrow.right")' not in display


def test_fixed_window_height_includes_the_complete_keypad_and_bottom_inset() -> None:
    layout = (ROOT / "Sources/MathAnchor/Views/CalculatorLayout.swift").read_text()
    content = (ROOT / "Sources/MathAnchor/Views/ContentView.swift").read_text()
    configurator = (
        ROOT / "Sources/MathAnchor/Support/CalculatorWindowConfigurator.swift"
    ).read_text()

    # Negative regression: the prior hand-entered heights exactly matched the
    # nominal row sum but clipped the last row in the real rounded app window.
    assert "static let keypadBottomInset: CGFloat = 20" in layout
    assert "keyHeight * 5 + keySpacing * 4" in layout
    assert "headerHeight + displayHeight + displayKeypadSpacing + keypadHeight + keypadBottomInset" in layout
    assert (
        "headerHeight + conversionDisplayHeight + displayKeypadSpacing + keypadHeight + keypadBottomInset"
        in layout
    )
    assert content.count(".padding(.bottom, CalculatorLayout.keypadBottomInset)") == 2
    # Negative regression: after inserting fullSizeContentView, asking AppKit
    # for frameRect(forContentRect:) discarded the titlebar safe area on the
    # first mode switch and shrank a 524 pt window to 492 pt.
    assert "window.frame.height - window.contentLayoutRect.height" in configurator
    assert "height: contentSize.height + chromeHeight" in configurator
    assert "let targetWindowSize = window.frameRect" not in configurator
    assert "window.minSize = targetWindowSize" in configurator
    assert "window.maxSize = targetWindowSize" in configurator


def test_conversion_keeps_currency_status_human_facing_and_agent_catalog_unchanged() -> None:
    runtime = (ROOT / "Sources/MathAnchorCore/Services/MathRuntimeService.swift").read_text()
    status = (ROOT / "Sources/MathAnchor/Views/CurrencyRateStatusView.swift").read_text()
    registry = (ROOT / "src/math_anchor/catalog.py").read_text()

    assert 'operation: "units.convert"' in runtime
    assert 'operation: "currency.convert"' in runtime
    assert 'Text("ECB")' in status
    assert 'detailRow("Published"' in status
    assert 'detailRow("Checked"' in status
    assert 'detailRow("Expires"' in status
    assert 'return ("EXPIRED"' in status
    assert "not a transaction quote" in status
    assert 'id="currency.convert"' not in registry


def test_conversion_catalog_includes_data_and_engineering_units() -> None:
    catalog = (ROOT / "Sources/MathAnchorCore/Models/UnitDefinition.swift").read_text()

    for category in (
        "case data",
        'case dataRate = "data rate"',
        "case frequency",
        "case force",
        "case acceleration",
        "case torque",
        "case density",
    ):
        assert category in catalog
    for stable_id in (
        'unit("gibibyte"',
        'unit("megabit-per-second"',
        '"standard-gravity"',
        'unit("newton-meter"',
        '"kilogram-per-cubic-meter"',
    ):
        assert stable_id in catalog


def test_conversion_popovers_and_text_editing_own_keyboard_focus() -> None:
    keyboard = (
        ROOT / "Sources/MathAnchor/Support/CalculatorKeyboardMonitor.swift"
    ).read_text()
    content = (ROOT / "Sources/MathAnchor/Views/ContentView.swift").read_text()
    transition = (
        ROOT / "Sources/MathAnchorCore/Support/CalculatorModeTransition.swift"
    ).read_text()
    commands = (ROOT / "Sources/MathAnchor/App/CalculatorCommands.swift").read_text()

    assert "shouldDeferToFocusedTextInput" in keyboard
    assert "conversionStore.dismissActivePopover()" in keyboard
    assert "modeTransition.select" in content
    assert "modeTransition.toggleModeMenu" in content
    assert "isPopoverDismissalSettling" in transition
    assert "Task.sleep(for: delay)" in transition
    assert transition.index("conversionStore.dismissActivePopover()") < transition.index("deferAction")
    assert transition.index("deferAction") < transition.index("calculatorStore.selectMode(mode)")
    assert "store.selectMode(" not in commands
    assert commands.count("modeTransition.select(") == 3
