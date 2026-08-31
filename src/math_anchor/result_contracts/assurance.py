from __future__ import annotations

from ..models import ASSURANCE_LEVELS


BACKEND_PROVENANCE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "name": {"type": "string", "minLength": 1, "maxLength": 64},
        "version": {"type": "string", "minLength": 1, "maxLength": 64},
    },
    "required": ["name", "version"],
}
PROVENANCE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "runtime": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "name": {"const": "math-anchor"},
                "version": {"type": "string", "minLength": 1, "maxLength": 64},
            },
            "required": ["name", "version"],
        },
        "backends": {
            "type": "array",
            "minItems": 1,
            "maxItems": 8,
            "items": BACKEND_PROVENANCE_SCHEMA,
        },
    },
    "required": ["runtime", "backends"],
}
CERTIFICATE_OR_NULL_SCHEMA = {
    "oneOf": [
        {"type": "null"},
        {"type": "object", "minProperties": 1, "maxProperties": 32},
    ]
}
CHECKED_BY_OR_NULL_SCHEMA = {
    "oneOf": [
        {"type": "null"},
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "system": {"type": "string", "minLength": 1, "maxLength": 64},
                "version": {"type": "string", "minLength": 1, "maxLength": 128},
                "artifactDigest": {
                    "type": "string",
                    "pattern": r"^sha256:[0-9a-f]{64}$",
                },
            },
            "required": ["system", "version", "artifactDigest"],
        },
    ]
}
BASE_ASSURANCE_PROPERTIES = {
    "assurance": {"enum": list(ASSURANCE_LEVELS)},
    "claim": {"type": "string", "minLength": 1, "maxLength": 128},
    "scope": {"type": "string", "minLength": 1, "maxLength": 128},
    "assumptions": {
        "type": "array",
        "maxItems": 32,
        "items": {"type": "string", "maxLength": 512},
    },
    "provenance": PROVENANCE_SCHEMA,
    "certificate": CERTIFICATE_OR_NULL_SCHEMA,
    "checkedBy": CHECKED_BY_OR_NULL_SCHEMA,
}
