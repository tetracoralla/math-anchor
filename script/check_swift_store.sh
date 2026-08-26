#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/script/swift_env.sh"
configure_swift_environment "$ROOT_DIR"
OUTPUT_DIR="$ROOT_DIR/.build/checks"
OUTPUT="$OUTPUT_DIR/CalculatorStoreChecks"

mkdir -p "$OUTPUT_DIR"

swiftc \
  -sdk "$SDKROOT" \
  -target "$MATH_ANCHOR_SWIFT_TARGET" \
  -package-name MathAnchor \
  -module-cache-path "$ROOT_DIR/.build/ModuleCache" \
  -parse-as-library \
  "$ROOT_DIR/Sources/MathAnchorCore/Models/CalculatorMode.swift" \
  "$ROOT_DIR/Sources/MathAnchorCore/Models/HistoryEntry.swift" \
  "$ROOT_DIR/Sources/MathAnchorCore/Models/EvaluationResult.swift" \
  "$ROOT_DIR/Sources/MathAnchorCore/Models/UnitDefinition.swift" \
  "$ROOT_DIR/Sources/MathAnchorCore/Models/UnitConversionResult.swift" \
  "$ROOT_DIR/Sources/MathAnchorCore/Models/CurrencyConversionResult.swift" \
  "$ROOT_DIR/Sources/MathAnchorCore/Services/MathEvaluating.swift" \
  "$ROOT_DIR/Sources/MathAnchorCore/Services/UnitConverting.swift" \
  "$ROOT_DIR/Sources/MathAnchorCore/Services/CurrencyConverting.swift" \
  "$ROOT_DIR/Sources/MathAnchorCore/Services/ClipboardWriting.swift" \
  "$ROOT_DIR/Sources/MathAnchorCore/Services/MathRuntimeService.swift" \
  "$ROOT_DIR/Sources/MathAnchorCore/Support/ExpressionEditing.swift" \
  "$ROOT_DIR/Sources/MathAnchorCore/Support/ConversionDisplayFormatting.swift" \
  "$ROOT_DIR/Sources/MathAnchorCore/Support/MathDisplayFormatting.swift" \
  "$ROOT_DIR/Sources/MathAnchor/Support/CalculatorKeyboardMonitor.swift" \
  "$ROOT_DIR/Sources/MathAnchorCore/Support/CalculatorModeTransition.swift" \
  "$ROOT_DIR/Sources/MathAnchorCore/Stores/HistoryStore.swift" \
  "$ROOT_DIR/Sources/MathAnchorCore/Stores/CalculatorStore.swift" \
  "$ROOT_DIR/Sources/MathAnchorCore/Stores/UnitConversionStore.swift" \
  "$ROOT_DIR/tests/CalculatorStoreChecks.swift" \
  -o "$OUTPUT"

"$OUTPUT"
