from __future__ import annotations

from .shared import (
    OperationSpec,
    _DECIMAL_TEXT,
    _PRECISION,
    _object,
    data,
    quantity,
    units,
)
from ..operations.units import CALENDAR_POLICIES, UNIT_CATEGORIES


SPECS = (
    OperationSpec(
        id="units.search",
        category="units",
        summary="Discover stable unit IDs and exact runtime spellings.",
        description="Search Math Anchor's curated unit catalog before converting. Returned IDs are stable inputs to units.convert; runtimeUnit is available for compound quantity expressions.",
        input_schema=_object(
            {
                "query": {"type": "string", "maxLength": 128, "default": ""},
                "category": {"type": "string", "enum": list(UNIT_CATEGORIES)},
                "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 20},
            },
            (),
        ),
        examples=(
            {"query": "兆字节"},
            {"category": "torque"},
            {"query": "Mbps"},
        ),
        handler=units.search,
        keywords=("unit catalog", "unit id", "measurement discovery", "单位目录", "查找单位", "数据量", "频率", "力", "扭矩", "密度"),
        backends=("python",),
    ),
    OperationSpec(
        id="units.convert",
        category="units",
        summary="Convert a physical quantity between compatible units.",
        description="Use Pint for dimensional conversion and claim an exact result only when the source value and full conversion path are rational.",
        input_schema=_object(
            {
                "value": {"oneOf": [{"type": "number"}, _DECIMAL_TEXT]},
                "fromUnit": {"type": "string", "maxLength": 128},
                "toUnit": {"type": "string", "maxLength": 128},
                "calendarPolicy": {
                    "type": "string",
                    "enum": list(CALENDAR_POLICIES),
                    "default": "reject",
                    "description": "Reject civil months/years by default; average_duration explicitly selects fixed average lengths.",
                },
                "precision": _PRECISION,
            },
            ("value", "fromUnit", "toUnit"),
        ),
        examples=(
            {"value": 72, "fromUnit": "watt", "toUnit": "kilowatt"},
            {"value": 68, "fromUnit": "degF", "toUnit": "degC"},
            {"value": 100, "fromUnit": "megabit-per-second", "toUnit": "megabyte-per-second"},
        ),
        handler=data.units_convert,
        keywords=("measurement", "dimension", "temperature", "length", "energy", "单位换算", "单位转换", "温度转换"),
        backends=("pint", "sympy"),
    ),
    OperationSpec(
        id="quantity.evaluate",
        category="units",
        summary="Evaluate arithmetic over unit-bearing quantities.",
        description="Parse a small unit-expression grammar with explicit multiplication, division, parentheses, and integer powers; enforce dimensional compatibility and optionally convert the result.",
        input_schema=_object(
            {
                "expression": {
                    "type": "string",
                    "maxLength": 2048,
                    "description": "Unit-bearing expression such as 80 * kg * 9.81 * m / s^2. Multiplication must be explicit.",
                },
                "toUnit": {"type": "string", "maxLength": 128},
                "calendarPolicy": {
                    "type": "string",
                    "enum": list(CALENDAR_POLICIES),
                    "default": "reject",
                },
                "precision": _PRECISION,
            },
            ("expression",),
        ),
        examples=(
            {"expression": "80 * kg * 9.81 * m / s^2", "toUnit": "newton"},
            {"expression": "3 * meter + 25 * centimeter", "toUnit": "meter"},
        ),
        handler=quantity.evaluate,
        backends=("pint", "sympy"),
        keywords=("dimensional analysis", "unit expression", "force", "compound units", "带单位表达式", "带单位的表达式", "量纲分析", "维度单位", "单位运算"),
    ),
)

SPECS_BY_ID = {spec.id: spec for spec in SPECS}
