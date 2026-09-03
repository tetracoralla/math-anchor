from __future__ import annotations

from .shared import _ok_schema


_COORDINATES = {
    "type": "array",
    "minItems": 2,
    "maxItems": 6,
    "uniqueItems": True,
    "items": {"type": "string"},
}
_MATRIX_WITNESS = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "row": {"type": "string"},
        "column": {"type": "string"},
        "exact": {"type": "string", "maxLength": 4096},
    },
    "required": ["row", "column", "exact"],
}
_NIJENHUIS_WITNESS = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "output": {"type": "string"},
        "left": {"type": "string"},
        "right": {"type": "string"},
        "exact": {"type": "string", "maxLength": 4096},
    },
    "required": ["output", "left", "right", "exact"],
}


RESULT_VARIANTS = (
    _ok_schema(
        "local_almost_complex_check",
        {
            "coordinates": _COORDINATES,
            "dimension": {"type": "integer", "enum": [2, 4, 6]},
            "matrixConvention": {"const": "row_output_column_input"},
            "frame": {"const": "commuting_coordinate_basis"},
            "nijenhuisConvention": {"const": "standard_unscaled_bracket"},
            "coefficientDomain": {"const": "rational_polynomials"},
            "square": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "satisfied": {"type": "boolean"},
                    "nonzeroComponentCount": {"type": "integer", "minimum": 0, "maximum": 36},
                    "firstNonzero": {"oneOf": [_MATRIX_WITNESS, {"type": "null"}]},
                },
                "required": ["satisfied", "nonzeroComponentCount", "firstNonzero"],
            },
            "nijenhuis": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "vanished": {"type": "boolean"},
                    "independentComponentsChecked": {"type": "integer", "minimum": 2, "maximum": 90},
                    "nonzeroComponentCount": {"type": "integer", "minimum": 0, "maximum": 90},
                    "firstNonzero": {"oneOf": [_NIJENHUIS_WITNESS, {"type": "null"}]},
                },
                "required": [
                    "vanished",
                    "independentComponentsChecked",
                    "nonzeroComponentCount",
                    "firstNonzero",
                ],
            },
            "localConclusion": {
                "enum": [
                    "not_almost_complex",
                    "almost_complex_nonintegrable_on_supplied_chart",
                    "integrability_conditions_satisfied_on_supplied_chart",
                ]
            },
            "uncheckedGlobalObligations": {
                "type": "array",
                "minItems": 1,
                "maxItems": 8,
                "uniqueItems": True,
                "items": {
                    "enum": [
                        "chart_domain_and_coverage",
                        "overlap_compatibility",
                        "global_smooth_extension",
                        "global_topological_and_analytic_existence",
                    ]
                },
            },
            "assurance": {"const": "deterministic"},
            "scope": {"const": "local_coordinate_rational_polynomial_almost_complex_check"},
        },
        [
            "coordinates",
            "dimension",
            "matrixConvention",
            "frame",
            "nijenhuisConvention",
            "coefficientDomain",
            "square",
            "nijenhuis",
            "localConclusion",
            "uncheckedGlobalObligations",
        ],
    ),
)
