from __future__ import annotations

from .shared import OperationSpec, _EXPRESSION, _object, certificate


SPECS = (
    OperationSpec(
        id="certificate.polynomial_identity",
        category="verification",
        summary="Generate an independently checkable rational polynomial identity certificate.",
        description=(
            "Normalize two bounded polynomial expressions over rational coefficients, return their exact "
            "difference coefficients, and bind the statement plus certificate with SHA-256 digests. The "
            "separate stdlib checker must still validate the certificate; this is not a proof-kernel result."
        ),
        input_schema=_object(
            {
                "left": _EXPRESSION,
                "right": _EXPRESSION,
                "variables": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "pattern": r"^[A-Za-z_][A-Za-z0-9_]*$",
                        "maxLength": 64,
                    },
                    "minItems": 1,
                    "maxItems": 8,
                    "uniqueItems": True,
                },
            },
            ("left", "right", "variables"),
        ),
        examples=(
            {
                "left": "(x + y)^2",
                "right": "x^2 + 2*x*y + y^2",
                "variables": ["x", "y"],
            },
            {
                "left": "x^2 - 1",
                "right": "(x - 1)*(x + 1) + 1",
                "variables": ["x"],
            },
        ),
        handler=certificate.polynomial_identity,
        keywords=(
            "polynomial identity certificate",
            "checkable algebra witness",
            "rational polynomial",
            "多项式恒等式证书",
            "可检查代数证据",
        ),
        assurance="certified",
        assurance_scope="polynomial_identity_over_rationals",
        backends=("sympy",),
    ),
)

SPECS_BY_ID = {spec.id: spec for spec in SPECS}
