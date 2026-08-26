from __future__ import annotations

from .shared import (
    OperationSpec,
    _object,
    combinatorics,
)


SPECS = (
    OperationSpec(
        id="combinatorics.count",
        category="combinatorics",
        summary="Compute an exact combination, permutation, or multinomial count.",
        description="Return one bounded exact combinatorial count with an explicit counting convention.",
        input_schema={
            "oneOf": [
                _object(
                    {
                        "action": {"type": "string", "enum": ["binomial", "permutations"]},
                        "n": {"type": "integer", "minimum": 0, "maximum": 5_000},
                        "k": {"type": "integer", "minimum": 0, "maximum": 5_000},
                    },
                    ("action", "n", "k"),
                ),
                _object(
                    {
                        "action": {"const": "multinomial"},
                        "counts": {
                            "type": "array",
                            "items": {"type": "integer", "minimum": 0, "maximum": 5_000},
                            "minItems": 1,
                            "maxItems": 128,
                        },
                    },
                    ("action", "counts"),
                ),
            ]
        },
        examples=(
            {"action": "binomial", "n": 52, "k": 5},
            {"action": "multinomial", "counts": [2, 3, 1]},
        ),
        handler=combinatorics.count,
        keywords=("combination", "permutation", "multinomial", "choose", "组合数", "排列数", "多项式系数"),
    ),
)

SPECS_BY_ID = {spec.id: spec for spec in SPECS}
