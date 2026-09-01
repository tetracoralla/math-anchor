from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

from math_anchor.catalog import OPERATIONS
from math_anchor.runtime import execute_direct


ROOT = Path(__file__).resolve().parents[2]


def test_catalog_import_does_not_load_unselected_heavy_engines() -> None:
    code = (
        "import json,sys; import math_anchor.runtime; "
        "print(json.dumps({name: name in sys.modules for name in ('sympy','numpy','pint','mpmath')}))"
    )
    environment = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(completed.stdout) == {
        "sympy": False,
        "numpy": False,
        "pint": False,
        "mpmath": False,
    }


def test_lazy_handler_preserves_provenance_and_loads_only_on_execution() -> None:
    spec = OPERATIONS["integer.machine_arithmetic"]
    assert spec.handler.__module__ == "math_anchor.operations.programmer"
    assert spec.handler.__name__ == "machine_arithmetic"

    result = execute_direct(
        "integer.machine_arithmetic",
        {
            "action": "add",
            "left": "250",
            "right": "20",
            "bitWidth": 8,
            "overflowBehavior": "wrapping",
        },
    )

    assert result["result"]["decimal"] == "14"
    assert result["provenance"]["entrypoint"] == "programmer.machine_arithmetic"
