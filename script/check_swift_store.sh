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
  -module-cache-path "$ROOT_DIR/.build/ModuleCache" \
  -parse-as-library \
  "$ROOT_DIR/Sources/MathAnchor/Models/CalculatorMode.swift" \
  "$ROOT_DIR/Sources/MathAnchor/Models/HistoryEntry.swift" \
  "$ROOT_DIR/Sources/MathAnchor/Models/EvaluationResult.swift" \
  "$ROOT_DIR/Sources/MathAnchor/Models/UnitDefinition.swift" \
  "$ROOT_DIR/Sources/MathAnchor/Models/UnitConversionResult.swift" \
  "$ROOT_DIR/Sources/MathAnchor/Models/CurrencyConversionResult.swift" \
  "$ROOT_DIR/Sources/MathAnchor/Services/MathEvaluating.swift" \
  "$ROOT_DIR/Sources/MathAnchor/Services/UnitConverting.swift" \
  "$ROOT_DIR/Sources/MathAnchor/Services/CurrencyConverting.swift" \
  "$ROOT_DIR/Sources/MathAnchor/Services/ClipboardWriting.swift" \
  "$ROOT_DIR/Sources/MathAnchor/Services/MathRuntimeService.swift" \
  "$ROOT_DIR/Sources/MathAnchor/Support/ExpressionEditing.swift" \
  "$ROOT_DIR/Sources/MathAnchor/Support/ConversionDisplayFormatting.swift" \
  "$ROOT_DIR/Sources/MathAnchor/Support/MathDisplayFormatting.swift" \
  "$ROOT_DIR/Sources/MathAnchor/Support/CalculatorKeyboardMonitor.swift" \
  "$ROOT_DIR/Sources/MathAnchor/Stores/HistoryStore.swift" \
  "$ROOT_DIR/Sources/MathAnchor/Stores/CalculatorStore.swift" \
  "$ROOT_DIR/Sources/MathAnchor/Stores/UnitConversionStore.swift" \
  "$ROOT_DIR/tests/CalculatorStoreChecks.swift" \
  -o "$OUTPUT"

"$OUTPUT"
