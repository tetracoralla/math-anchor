from __future__ import annotations

from copy import deepcopy

from .common import RESULT_VARIANTS as _COMMON
from .integers import RESULT_VARIANTS as _INTEGERS
from .linear_algebra import RESULT_VARIANTS as _LINEAR_ALGEBRA
from .calculus import RESULT_VARIANTS as _CALCULUS
from .data_science import RESULT_VARIANTS as _DATA_SCIENCE
from .numerical_finance import RESULT_VARIANTS as _NUMERICAL_FINANCE
from .shared import ERROR_RESULT_SCHEMA, _SCHEMA_DEFINITIONS


RUN_RESULT_SCHEMA = {
    "oneOf": [
        *_COMMON,
    *_INTEGERS,
    *_LINEAR_ALGEBRA,
    *_CALCULUS,
    *_DATA_SCIENCE,
    *_NUMERICAL_FINANCE,
    ],
    "$defs": deepcopy(_SCHEMA_DEFINITIONS),
}
