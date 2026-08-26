from __future__ import annotations

from .shared import (
    OperationSpec,
    _EXACT_MATRIX,
    _EXACT_VECTOR,
    _MATRIX,
    _PRECISION,
    _object,
    linear_algebra,
    matrix,
)


SPECS = (
    OperationSpec(
        id="matrix.determinant",
        category="matrix",
        summary="Compute a square matrix determinant.",
        description="Compute the exact determinant of a square matrix.",
        input_schema=_object({"matrix": _MATRIX, "precision": _PRECISION}, ("matrix",)),
        examples=({"matrix": [[1, 2], [3, 4]]},),
        handler=matrix.determinant,
        keywords=("linear algebra", "det", "行列式", "矩阵"),
    ),
    OperationSpec(
        id="matrix.inverse",
        category="matrix",
        summary="Invert a nonsingular square matrix.",
        description="Return a square matrix inverse under the caller's exact/approximate output selection and strict byte budget.",
        input_schema=_object({"matrix": _MATRIX, "precision": _PRECISION}, ("matrix",)),
        examples=({"matrix": [[1, 2], [3, 4]]},),
        handler=matrix.inverse,
        keywords=("linear algebra", "reciprocal matrix", "逆矩阵", "矩阵求逆"),
    ),
    OperationSpec(
        id="matrix.eigenvalues",
        category="matrix",
        summary="Compute square matrix eigenvalues.",
        description="Return eigenvalues with multiplicity, preserving exact values when SymPy can derive them.",
        input_schema=_object({"matrix": _MATRIX, "precision": _PRECISION}, ("matrix",)),
        examples=({"matrix": [[2, 0], [0, 3]]},),
        handler=matrix.eigenvalues,
        keywords=("linear algebra", "spectrum", "characteristic", "特征值", "矩阵特征值"),
    ),
    OperationSpec(
        id="matrix.solve",
        category="matrix",
        summary="Solve one exact linear system A x = b.",
        description="Classify an exact linear system as unique, inconsistent, or infinite and return a particular solution plus nullspace basis when applicable.",
        input_schema=_object(
            {
                "matrix": _EXACT_MATRIX,
                "constants": _EXACT_VECTOR,
                "variables": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                    "maxItems": 50,
                },
                "precision": _PRECISION,
            },
            ("matrix", "constants"),
        ),
        examples=(
            {"matrix": [[1, 1], [1, -1]], "constants": [7, 1], "variables": ["x", "y"]},
            {"matrix": [[1, 2], [2, 4]], "constants": [3, 6]},
        ),
        handler=matrix.solve,
        keywords=("linear system", "Ax=b", "simultaneous equations", "线性方程组", "矩阵求解", "增广矩阵"),
    ),
    OperationSpec(
        id="matrix.reduce",
        category="matrix",
        summary="Compute exact matrix structure, eigenspaces, or a decomposition.",
        description="Compute rank, RREF, nullspace, column space, eigenspaces with diagonalizability, LU, or Cholesky over exact entries; approximate floating entries are rejected.",
        input_schema=_object(
            {
                "action": {"type": "string", "enum": ["rank", "rref", "nullspace", "columnspace", "eigenspaces", "lu", "cholesky"]},
                "matrix": _EXACT_MATRIX,
                "precision": _PRECISION,
            },
            ("action", "matrix"),
        ),
        examples=(
            {"action": "rref", "matrix": [[1, 2, 3], [2, 4, 6]]},
            {"action": "nullspace", "matrix": [[1, 2], [2, 4]]},
            {"action": "eigenspaces", "matrix": [[2, 1], [0, 2]]},
            {"action": "cholesky", "matrix": [[4, 2], [2, 3]]},
        ),
        handler=matrix.reduce,
        keywords=("rank", "row reduce", "RREF", "null space", "column space", "eigenvectors", "eigenspaces", "diagonalizable", "LU", "Cholesky", "秩", "行最简形", "零空间", "列空间", "特征向量", "特征空间", "可对角化", "LU分解", "Cholesky分解"),
    ),
    OperationSpec(
        id="linear_algebra.exact",
        category="matrix",
        summary="Run exact matrix multiplication, transpose, or vector algebra.",
        description="Keep integer and symbolic-rational inputs on the exact SymPy path for matrix multiplication and transpose; vector actions require provably real exact entries so norms and projections retain unambiguous Euclidean semantics.",
        input_schema={
            "oneOf": [
                _object(
                    {
                        "action": {"const": "matrix_multiply"},
                        "left": _EXACT_MATRIX,
                        "right": _EXACT_MATRIX,
                        "precision": _PRECISION,
                    },
                    ("action", "left", "right"),
                ),
                _object(
                    {
                        "action": {"const": "transpose"},
                        "matrix": _EXACT_MATRIX,
                        "precision": _PRECISION,
                    },
                    ("action", "matrix"),
                ),
                _object(
                    {
                        "action": {"type": "string", "enum": ["dot", "cross"]},
                        "left": _EXACT_VECTOR,
                        "right": _EXACT_VECTOR,
                        "precision": _PRECISION,
                    },
                    ("action", "left", "right"),
                ),
                _object(
                    {
                        "action": {"type": "string", "enum": ["norm", "norm_squared"]},
                        "vector": _EXACT_VECTOR,
                        "precision": _PRECISION,
                    },
                    ("action", "vector"),
                ),
                _object(
                    {
                        "action": {"const": "projection"},
                        "left": _EXACT_VECTOR,
                        "onto": _EXACT_VECTOR,
                        "precision": _PRECISION,
                    },
                    ("action", "left", "onto"),
                ),
            ]
        },
        examples=(
            {"action": "matrix_multiply", "left": [[1, 2], [3, 4]], "right": [[2], [1]]},
            {"action": "cross", "left": [1, 0, 0], "right": [0, 1, 0]},
            {"action": "projection", "left": [2, 2], "onto": [1, 0]},
        ),
        handler=linear_algebra.exact,
        keywords=("matrix multiplication", "transpose", "dot product", "cross product", "vector norm", "projection", "矩阵乘法", "转置", "点积", "叉积", "向量范数", "投影"),
    ),
)

SPECS_BY_ID = {spec.id: spec for spec in SPECS}
