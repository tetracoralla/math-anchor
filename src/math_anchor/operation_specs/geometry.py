from __future__ import annotations

from .shared import OperationSpec, _object, geometry


_COORDINATES = {
    "type": "array",
    "items": {
        "type": "string",
        "pattern": r"^[A-Za-z_][A-Za-z0-9_]*$",
        "maxLength": 64,
    },
    "minItems": 2,
    "maxItems": 6,
    "uniqueItems": True,
    "description": "Ordered local coordinate names; the dimension must be even.",
}
_POLYNOMIAL_ENTRY = {
    "type": "string",
    "minLength": 1,
    "maxLength": 1024,
    "description": "Rational-polynomial component using the declared coordinates.",
}
_STRUCTURE = {
    "type": "array",
    "minItems": 2,
    "maxItems": 6,
    "items": {
        "type": "array",
        "minItems": 2,
        "maxItems": 6,
        "items": _POLYNOMIAL_ENTRY,
    },
    "description": (
        "Square component matrix in row-output, column-input convention: "
        "structure[k][i] is the coefficient J^k_i in J(partial_i)."
    ),
}


SPECS = (
    OperationSpec(
        id="geometry.almost_complex.local_check",
        category="geometry",
        summary="Check a rational-polynomial local almost-complex candidate and its Nijenhuis tensor.",
        description=(
            "Given one ordered coordinate chart and a square component matrix J^k_i, exactly check "
            "J^2 = -I and the independent coordinate-basis components of the unscaled convention "
            "N(X,Y)=[JX,JY]-J[JX,Y]-J[X,JY]+J^2[X,Y] over rational polynomials. Returns the first "
            "counterexample component and explicit unchecked "
            "global obligations. This local check does not establish chart coverage, overlap "
            "compatibility, global smooth extension, or existence of a complex structure on a manifold."
        ),
        input_schema=_object(
            {
                "coordinates": _COORDINATES,
                "structure": _STRUCTURE,
            },
            ("coordinates", "structure"),
        ),
        examples=(
            {
                "coordinates": ["x", "y"],
                "structure": [["0", "-1"], ["1", "0"]],
            },
            {
                "coordinates": ["x0", "x1", "x2", "x3"],
                "structure": [
                    ["0", "-1", "0", "-x0"],
                    ["1", "0", "-x0", "0"],
                    ["0", "0", "0", "-1"],
                    ["0", "0", "1", "0"],
                ],
            },
        ),
        handler=geometry.almost_complex_local_check,
        keywords=(
            "almost complex structure",
            "Nijenhuis tensor",
            "local integrability",
            "complex manifold candidate",
            "differential geometry tensor",
            "几乎复结构",
            "Nijenhuis 张量",
            "局部可积性",
        ),
        assurance="deterministic",
        assurance_scope="local_coordinate_rational_polynomial_almost_complex_check",
        backends=("sympy",),
    ),
)


SPECS_BY_ID = {spec.id: spec for spec in SPECS}
