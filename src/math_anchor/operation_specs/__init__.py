from __future__ import annotations

from .expression import SPECS_BY_ID as _EXPRESSION
from .decimal import SPECS_BY_ID as _DECIMAL
from .verification import SPECS_BY_ID as _VERIFICATION
from .algebra import SPECS_BY_ID as _ALGEBRA
from .calculus import SPECS_BY_ID as _CALCULUS
from .numeric import SPECS_BY_ID as _NUMERIC
from .integer import SPECS_BY_ID as _INTEGER
from .combinatorics import SPECS_BY_ID as _COMBINATORICS
from .matrix import SPECS_BY_ID as _MATRIX
from .statistics import SPECS_BY_ID as _STATISTICS
from .probability import SPECS_BY_ID as _PROBABILITY
from .measurement import SPECS_BY_ID as _MEASUREMENT
from .units import SPECS_BY_ID as _UNITS
from .dimension import SPECS_BY_ID as _DIMENSION
from .finance import SPECS_BY_ID as _FINANCE

_GROUPS = (
    _EXPRESSION,
    _DECIMAL,
    _VERIFICATION,
    _ALGEBRA,
    _CALCULUS,
    _NUMERIC,
    _INTEGER,
    _COMBINATORICS,
    _MATRIX,
    _STATISTICS,
    _PROBABILITY,
    _MEASUREMENT,
    _UNITS,
    _DIMENSION,
    _FINANCE,
)
_BY_ID = {operation_id: spec for group in _GROUPS for operation_id, spec in group.items()}
_ORDER = (
    'expression.evaluate',
    'expression.simplify',
    'decimal.quantize',
    'function.sample',
    'expression.equivalent',
    'algebra.transform',
    'algebra.solve',
    'solution.verify',
    'calculus.derivative',
    'calculus.integrate',
    'calculus.limit',
    'calculus.series',
    'calculus.multivariate',
    'numeric.root',
    'numeric.integrate',
    'numeric.minimize',
    'integer.factorization',
    'integer.gcd_lcm',
    'integer.modular',
    'integer.divide',
    'integer.represent',
    'integer.bitwise',
    'integer.machine_arithmetic',
    'float.ieee754',
    'combinatorics.count',
    'matrix.determinant',
    'matrix.inverse',
    'matrix.eigenvalues',
    'matrix.solve',
    'matrix.solve_approximate',
    'matrix.reduce',
    'linear_algebra.exact',
    'linear_algebra.numeric',
    'statistics.describe',
    'statistics.infer',
    'probability.distribution',
    'measurement.propagate',
    'units.search',
    'units.convert',
    'quantity.evaluate',
    'dimension.check',
    'dimension.infer',
    'dimension.pi_groups',
    'finance.calculate',
)

ALL_SPECS = tuple(_BY_ID[operation_id] for operation_id in _ORDER)
