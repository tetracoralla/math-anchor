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
  -target "$ZIBETHA_SWIFT_TARGET" \
  -module-cache-path "$ROOT_DIR/.build/ModuleCache" \
  -parse-as-library \
  "$ROOT_DIR/Sources/Zibetha/Models/CalculatorMode.swift" \
  "$ROOT_DIR/Sources/Zibetha/Models/HistoryEntry.swift" \
  "$ROOT_DIR/Sources/Zibetha/Models/EvaluationResult.swift" \
  "$ROOT_DIR/Sources/Zibetha/Models/UnitDefinition.swift" \
  "$ROOT_DIR/Sources/Zibetha/Models/UnitConversionResult.swift" \
  "$ROOT_DIR/Sources/Zibetha/Models/CurrencyConversionResult.swift" \
  "$ROOT_DIR/Sources/Zibetha/Services/MathEvaluating.swift" \
  "$ROOT_DIR/Sources/Zibetha/Services/UnitConverting.swift" \
  "$ROOT_DIR/Sources/Zibetha/Services/CurrencyConverting.swift" \
  "$ROOT_DIR/Sources/Zibetha/Services/ClipboardWriting.swift" \
  "$ROOT_DIR/Sources/Zibetha/Services/MathRuntimeService.swift" \
  "$ROOT_DIR/Sources/Zibetha/Support/ExpressionEditing.swift" \
  "$ROOT_DIR/Sources/Zibetha/Support/ConversionDisplayFormatting.swift" \
  "$ROOT_DIR/Sources/Zibetha/Support/MathDisplayFormatting.swift" \
  "$ROOT_DIR/Sources/Zibetha/Support/CalculatorKeyboardMonitor.swift" \
  "$ROOT_DIR/Sources/Zibetha/Stores/HistoryStore.swift" \
  "$ROOT_DIR/Sources/Zibetha/Stores/CalculatorStore.swift" \
  "$ROOT_DIR/Sources/Zibetha/Stores/UnitConversionStore.swift" \
  "$ROOT_DIR/Tests/CalculatorStoreChecks.swift" \
  -o "$OUTPUT"

"$OUTPUT"
