from __future__ import annotations

from .shared import _ok_schema


_DIGEST = {"type": "string", "pattern": r"^sha256:[0-9a-f]{64}$"}
_VARIABLES = {
    "type": "array",
    "minItems": 1,
    "maxItems": 8,
    "uniqueItems": True,
    "items": {
        "type": "string",
        "pattern": r"^[A-Za-z_][A-Za-z0-9_]*$",
        "maxLength": 64,
    },
}
_CERTIFICATE = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "format": {"const": "math-anchor.polynomial-identity.v1"},
        "statement": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "left": {"type": "string", "maxLength": 4096},
                "right": {"type": "string", "maxLength": 4096},
                "variables": _VARIABLES,
            },
            "required": ["left", "right", "variables"],
        },
        "statementDigest": _DIGEST,
        "identity": {"type": "boolean"},
        "normalizedDifference": {
            "type": "array",
            "maxItems": 512,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "powers": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 8,
                        "items": {"type": "integer", "minimum": 0, "maximum": 64},
                    },
                    "coefficient": {
                        "type": "string",
                        "pattern": r"^-?(?:0|[1-9]\d*)(?:/[1-9]\d*)?$",
                    },
                },
                "required": ["powers", "coefficient"],
            },
        },
        "certificateDigest": _DIGEST,
    },
    "required": [
        "format",
        "statement",
        "statementDigest",
        "identity",
        "normalizedDifference",
        "certificateDigest",
    ],
}


RESULT_VARIANTS = (
    _ok_schema(
        "polynomial_identity_certificate",
        {
            "identity": {"type": "boolean"},
            "variables": _VARIABLES,
            "certificate": _CERTIFICATE,
            "checkedBy": {"type": "null"},
            "assurance": {"const": "certified"},
            "scope": {"const": "polynomial_identity_over_rationals"},
        },
        ["identity", "variables"],
    ),
)
