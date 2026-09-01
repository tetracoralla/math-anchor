from __future__ import annotations

from decimal import Decimal, ROUND_HALF_EVEN
from fractions import Fraction
import importlib.util
import json
import math
from pathlib import Path
import struct
from statistics import NormalDist
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
EVAL_DIR = ROOT / "evals" / "agent"


AGENT_EVAL_SPEC = importlib.util.spec_from_file_location(
    "math_anchor_agent_eval",
    ROOT / "script" / "agent_eval.py",
)
assert AGENT_EVAL_SPEC is not None and AGENT_EVAL_SPEC.loader is not None
agent_eval = importlib.util.module_from_spec(AGENT_EVAL_SPEC)
SCRIPT_DIR = str(ROOT / "script")
sys.path.insert(0, SCRIPT_DIR)
try:
    AGENT_EVAL_SPEC.loader.exec_module(agent_eval)
finally:
    sys.path.remove(SCRIPT_DIR)


def _load(name: str) -> dict:
    return json.loads((EVAL_DIR / name).read_text(encoding="utf-8"))


def _determinant_bareiss(matrix: list[list[int]]) -> int:
    values = [row[:] for row in matrix]
    sign = 1
    previous = 1
    for pivot_index in range(len(values) - 1):
        if values[pivot_index][pivot_index] == 0:
            swap = next(
                row
                for row in range(pivot_index + 1, len(values))
                if values[row][pivot_index] != 0
            )
            values[pivot_index], values[swap] = values[swap], values[pivot_index]
            sign *= -1
        pivot = values[pivot_index][pivot_index]
        for row in range(pivot_index + 1, len(values)):
            for column in range(pivot_index + 1, len(values)):
                values[row][column] = (
                    values[row][column] * pivot
                    - values[row][pivot_index] * values[pivot_index][column]
                ) // previous
        previous = pivot
    return sign * values[-1][-1]


def _fraction_rank(matrix: list[list[Fraction]]) -> int:
    values = [row[:] for row in matrix]
    rank = 0
    for column in range(len(values[0])):
        pivot = next(
            (row for row in range(rank, len(values)) if values[row][column] != 0),
            None,
        )
        if pivot is None:
            continue
        values[rank], values[pivot] = values[pivot], values[rank]
        divisor = values[rank][column]
        values[rank] = [value / divisor for value in values[rank]]
        for row in range(len(values)):
            if row == rank or values[row][column] == 0:
                continue
            factor = values[row][column]
            values[row] = [
                value - factor * pivot_value
                for value, pivot_value in zip(values[row], values[rank], strict=True)
            ]
        rank += 1
    return rank


def _cubic_root() -> float:
    value = 1.5
    for _ in range(20):
        value -= (value**3 - value - 2) / (3 * value**2 - 1)
    return value


def _expected_values() -> dict[str, object]:
    negative_zero_bits = struct.pack(">d", -0.0).hex()
    binary32_integer = int(struct.unpack(">f", struct.pack(">f", 16_777_217.0))[0])
    return {
        "machine.u8-wrapping-add": (250 + 20) % (1 << 8),
        "machine.i16-saturating-multiply": min(300 * 300, (1 << 15) - 1),
        "bits.rotate-left-u8": ((0x81 << 1) | (0x81 >> 7)) & 0xFF,
        "bits.extract-byte": (0xDEADBEEF >> 8) & 0xFF,
        "float.binary64-negative-zero": negative_zero_bits,
        "float.binary32-integer-rounding": binary32_integer,
        "float.binary64-ulp-distance": 1,
        "decimal.half-even-quantize": float(
            Decimal("2.675").quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
        ),
        "integer.euclidean-quotient": divmod(-17, 5)[0],
        "integer.modular-inverse": pow(65537, -1, 3120),
        "integer.binomial-100-50": str(math.comb(100, 50)),
        "integer.large-product": str(987654321 * 123456789),
        "matrix.determinant-4x4": _determinant_bareiss(
            [[17, 23, 5, 11], [31, 47, 13, 19], [2, 3, 7, 29], [37, 41, 43, 53]]
        ),
        "linear-algebra.minimum-norm-coordinate": 1,
        "units.gibibyte-to-bits": (1 << 30) * 8,
        "units.data-rate-to-bytes": 1_000_000_000 * 2.5 / 8,
        "units.force-newtons": 80 * 9.81,
        "units.density-si": 5 / 0.002,
        "measurement.correlated-sum": math.sqrt(3**2 + 4**2 + 2 * 3 * 4),
        "probability.normal-quantile": NormalDist().inv_cdf(0.975),
        "numeric.integral-sine": 2,
        "numeric.root-cubic": _cubic_root(),
        "finance.compound-future-value": float(Decimal(1000) * Decimal("1.05") ** 10),
        "dimension.energy-time-exponent": -2,
        "optional.simple-percentage": 200 * 0.17,
        "optional.simple-gcd": math.gcd(84, 126),
        "optional.celsius-to-fahrenheit": 20 * 9 / 5 + 32,
        "irrelevant.marker-string": "openadam-eval-marker",
        "irrelevant.language-name": "swift",
        "irrelevant.identifier-style": True,
    }


def test_coding_agent_suite_has_independent_oracles_and_balanced_opportunities() -> None:
    suite = _load("coding-agent-utility.v0.1.json")
    tasks = suite["tasks"]
    by_id = {task["id"]: task for task in tasks}
    assert len(tasks) == 30
    assert len(by_id) == 30
    assert suite["targetRef"] == {"id": "math-anchor", "version": "0.5.0"}
    assert {opportunity: sum(task["opportunity"] == opportunity for task in tasks) for opportunity in ("required", "optional", "irrelevant")} == {
        "required": 24,
        "optional": 3,
        "irrelevant": 3,
    }
    assert set(_expected_values()) == set(by_id)
    for task_id, expected in _expected_values().items():
        recorded = by_id[task_id]["evaluator"]["expected"]
        if isinstance(expected, float):
            assert math.isclose(float(recorded), expected, rel_tol=1e-15, abs_tol=1e-15)
        else:
            assert recorded == expected
    required_tags = {
        tag
        for task in tasks
        if task["opportunity"] == "required"
        for tag in task["tags"]
    }
    assert {"bitwise", "ieee754", "rounding", "exact", "least-squares", "units", "uncertainty", "probability", "calculus", "finance", "dimension"} <= required_tags
    assert all("math anchor" not in task["prompt"].lower() for task in tasks)
    assert all("math.run" not in task["prompt"].lower() for task in tasks)


def test_routing_smoke_is_an_exact_subset_of_the_utility_suite() -> None:
    full = {task["id"]: task for task in _load("coding-agent-utility.v0.1.json")["tasks"]}
    smoke = _load("routing-smoke.v0.1.json")
    assert len(smoke["tasks"]) == 4
    assert {task["opportunity"] for task in smoke["tasks"]} == {
        "required",
        "optional",
        "irrelevant",
    }
    for task in smoke["tasks"]:
        assert task == full[task["id"]]


def test_experiments_fix_one_agent_harness_driver_and_target() -> None:
    expectations = {
        "codex-luna-routing-smoke.v0.1.json": ("math-anchor.routing-smoke", "development-smoke", 1, 8),
        "codex-luna-policy-routing-smoke.v0.1.json": ("math-anchor.routing-smoke", "development-smoke", 1, 8),
        "codex-luna-installed-plugin-routing-smoke.v0.1.json": ("math-anchor.routing-smoke", "development-smoke", 1, 8),
        "codex-luna-utility.v0.1.json": ("math-anchor.coding-agent-utility", "utility-estimate", 3, 180),
        "codex-luna-policy-utility.v0.1.json": ("math-anchor.coding-agent-utility", "utility-estimate", 3, 180),
    }
    for filename, (suite_id, purpose, repeats, planned) in expectations.items():
        experiment = _load(filename)
        suite_name = (
            "routing-smoke.v0.1.json"
            if suite_id.endswith("routing-smoke")
            else "coding-agent-utility.v0.1.json"
        )
        task_count = len(_load(suite_name)["tasks"])
        assert experiment["suiteRef"] == {"id": suite_id, "version": "0.1.0"}
        assert experiment["targetRef"] == {"id": "math-anchor", "version": "0.5.0"}
        assert experiment["purpose"] == purpose
        assert experiment["repeats"] == repeats
        assert experiment["agent"] == {"provider": "openai", "model": "gpt-5.6-luna"}
        assert experiment["harness"] == {"id": "codex-cli", "version": "0.152.0"}
        assert experiment["driver"]["id"] == "codex-cli-driver"
        assert experiment["driver"]["version"] == "0.5.0"
        arguments = experiment["driver"]["args"]
        reasoning_index = arguments.index("--config") + 1
        assert arguments[reasoning_index] == 'model_reasoning_effort="low"'
        assert experiment["budget"]["maxToolCalls"] == 4
        assert task_count * repeats * len(experiment["conditions"]) == planned
        assert experiment["conditions"]["baseline"]["capabilityAvailable"] is False
        assert experiment["conditions"]["treatment"]["capabilityAvailable"] is True


def test_policy_assisted_experiments_use_one_provider_neutral_policy_in_both_conditions() -> None:
    for filename in (
        "codex-luna-policy-routing-smoke.v0.1.json",
        "codex-luna-policy-utility.v0.1.json",
    ):
        arguments = _load(filename)["driver"]["args"]
        policy_index = arguments.index("--shared-instructions-file") + 1
        assert arguments[policy_index] == "${MATH_ANCHOR_CODING_AGENT_POLICY}"
    policy_path = EVAL_DIR / "coding-agent-policy.md"
    policy = policy_path.read_text(encoding="utf-8").lower()
    assert "math anchor" not in policy
    assert "math.run" not in policy
    assert "trivial low-risk arithmetic" in policy


def test_research_smoke_pairs_terra_and_luna_with_the_same_direct_mcp_task() -> None:
    suite = _load("research-putnam-1976-a2.v0.1.json")
    assert suite["targetRef"] == {"id": "math-anchor", "version": "0.5.0"}
    assert len(suite["tasks"]) == 1
    assert suite["tasks"][0]["evaluator"]["expected"] == "2,63,90,3"
    assert suite["tasks"][0]["opportunity"] == "required"

    for model in ("terra", "luna"):
        experiment = _load(f"codex-{model}-research-putnam-1976-a2.v0.1.json")
        assert experiment["suiteRef"] == {
            "id": "math-anchor.research-putnam-1976-a2",
            "version": "0.1.0",
        }
        assert experiment["agent"] == {
            "provider": "openai",
            "model": f"gpt-5.6-{model}",
        }
        assert experiment["targetRef"] == {"id": "math-anchor", "version": "0.5.0"}
        assert experiment["harness"] == {"id": "codex-cli", "version": "0.152.0"}
        assert experiment["driver"]["version"] == "0.5.0"
        arguments = experiment["driver"]["args"]
        assert "--target-plugin-id" not in arguments
        assert "${MATH_ANCHOR_MCP_COMMAND}" in arguments
        assert "${MATH_ANCHOR_MCP_CWD}" in arguments
        assert "${MATH_ANCHOR_CODING_AGENT_POLICY}" in arguments
        assert len(experiment["conditions"]) * experiment["repeats"] == 2


def test_public_math_smoke_uses_independent_oracles_and_two_named_agents() -> None:
    suite = _load("research-public-math-smoke.v0.1.json")
    by_id = {task["id"]: task for task in suite["tasks"]}
    assert suite["targetRef"] == {"id": "math-anchor", "version": "0.5.0"}
    assert len(by_id) == 4

    assert by_id["putnam-2023-b1.m37-n64"]["evaluator"]["expected"] == str(
        math.comb(99, 36)
    )

    matrix = [
        [
            sum(
                1
                for a in range(12 // row + 1)
                for b in range(12 // column + 1)
                if a * row + b * column == 12
            )
            for column in range(1, 13)
        ]
        for row in range(1, 13)
    ]
    determinant = _determinant_bareiss(matrix)
    b6 = by_id["putnam-2023-b6.n12"]
    assert b6["evaluator"]["expected"] == determinant == -12
    assert f"S={json.dumps(matrix, separators=(',', ':'))}" in b6["prompt"]

    hilbert = [
        [Fraction(1, row + column + 1) for column in range(12)]
        for row in range(12)
    ]
    assert _fraction_rank(hilbert) == 12
    assert by_id["nist-hilbert-12.stability"]["evaluator"]["expected"] == (
        "ill_conditioned,12,null"
    )

    dimensions = [
        [1, -3, 1, 1, -1],
        [1, 1, -1, 0, -1],
        [-2, 0, 0, -1, -1],
    ]
    dimension_rank = _fraction_rank(
        [[Fraction(value) for value in row] for row in dimensions]
    )
    assert by_id["buckingham-pi.drag-nullity"]["evaluator"]["expected"] == (
        5 - dimension_rank
    ) == 2

    for task in suite["tasks"]:
        prompt = task["prompt"].lower()
        assert "math anchor" not in prompt
        assert "math.run" not in prompt
        assert "certificate.polynomial_identity" not in prompt

    for model in ("terra", "luna"):
        experiment = _load(f"codex-{model}-research-public-math-smoke.v0.1.json")
        assert experiment["suiteRef"] == {
            "id": suite["id"],
            "version": suite["version"],
        }
        assert experiment["agent"] == {
            "provider": "openai",
            "model": f"gpt-5.6-{model}",
        }
        assert experiment["harness"] == {"id": "codex-cli", "version": "0.152.0"}
        assert len(suite["tasks"]) * len(experiment["conditions"]) == 8


def test_installed_plugin_smoke_uses_one_isolated_target_plugin_without_policy_injection() -> None:
    experiment = _load("codex-luna-installed-plugin-routing-smoke.v0.1.json")
    arguments = experiment["driver"]["args"]
    home_index = arguments.index("--isolated-plugin-home") + 1
    assert arguments[home_index] == "${MATH_ANCHOR_ISOLATED_CODEX_HOME}"
    assert "--target-plugin-id" in arguments
    assert "math-anchor@openadam" in arguments
    assert "--shared-instructions-file" not in arguments
    assert experiment["budget"]["maxToolCalls"] == 4


def test_model_run_preflight_rejects_stale_codex_harness(monkeypatch) -> None:
    experiment = _load("codex-luna-installed-plugin-routing-smoke.v0.1.json")
    monkeypatch.setattr(agent_eval.shutil, "which", lambda _command: "/usr/local/bin/codex")
    monkeypatch.setattr(
        agent_eval.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            args=["codex", "--version"],
            returncode=0,
            stdout="codex-cli 99.0.0\n",
            stderr="",
        ),
    )

    with pytest.raises(SystemExit, match="declared Codex harness does not match"):
        agent_eval._validate_codex_harness(experiment)


def test_isolated_agent_environment_restores_home(monkeypatch) -> None:
    monkeypatch.setenv("HOME", "/tmp/math-anchor-original-home")

    with agent_eval._temporary_environment({"HOME": "/tmp/math-anchor-isolated-home"}):
        assert agent_eval.os.environ["HOME"] == "/tmp/math-anchor-isolated-home"

    assert agent_eval.os.environ["HOME"] == "/tmp/math-anchor-original-home"


def test_direct_mcp_pair_uses_one_temporary_empty_codex_home(
    monkeypatch, tmp_path: Path
) -> None:
    source_home = tmp_path / "source-codex"
    source_home.mkdir()
    auth = source_home / "auth.json"
    auth.write_text('{"token":"fixture"}', encoding="utf-8")
    monkeypatch.setenv("CODEX_HOME", str(source_home))
    monkeypatch.setenv("HOME", str(tmp_path / "original-home"))

    with agent_eval._isolated_direct_codex_home(True):
        isolated = Path(agent_eval.os.environ["CODEX_HOME"])
        assert agent_eval.os.environ["HOME"] == str(isolated)
        assert isolated != source_home
        assert (isolated / "auth.json").resolve() == auth.resolve()
        assert (isolated / "config.toml").read_text(encoding="utf-8") == ""

    assert agent_eval.os.environ["CODEX_HOME"] == str(source_home)
    assert agent_eval.os.environ["HOME"] == str(tmp_path / "original-home")


def test_static_research_validation_does_not_require_a_packaged_runtime(
    tmp_path: Path,
) -> None:
    experiment_path = EVAL_DIR / "codex-terra-research-putnam-1976-a2.v0.1.json"
    experiment = _load(experiment_path.name)

    with agent_eval._prepared_experiment(
        experiment_path,
        experiment,
        prepare_installed_plugin=False,
        prepare_direct_runtime=False,
    ) as prepared:
        prepared_experiment = json.loads(prepared.read_text(encoding="utf-8"))

    arguments = prepared_experiment["driver"]["args"]
    assert "${MATH_ANCHOR_MCP_COMMAND}" in arguments
    assert "${MATH_ANCHOR_MCP_CWD}" in arguments


def test_model_run_preparation_requires_the_packaged_direct_runtime(
    monkeypatch,
) -> None:
    experiment_path = EVAL_DIR / "codex-terra-research-putnam-1976-a2.v0.1.json"
    experiment = _load(experiment_path.name)
    monkeypatch.setattr(
        agent_eval,
        "PACKAGED_MCP_COMMAND",
        ROOT / "build" / "missing-math-anchor-runtime",
    )

    with pytest.raises(SystemExit, match="packaged Math Anchor MCP runtime is unavailable"):
        with agent_eval._prepared_experiment(
            experiment_path,
            experiment,
            prepare_installed_plugin=False,
            prepare_direct_runtime=True,
        ):
            pass


def test_direct_runtime_is_staged_outside_denied_source_root(
    monkeypatch,
    tmp_path: Path,
) -> None:
    bundle = tmp_path / "source-runtime"
    bundle.mkdir()
    executable = bundle / "math-anchor-runtime"
    executable.write_text("fixture", encoding="utf-8")
    executable.chmod(0o755)
    (bundle / ".math-anchor-build-manifest.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(agent_eval, "PACKAGED_MCP_COMMAND", executable)
    monkeypatch.setattr(agent_eval, "verify_manifest", lambda *_args: None)
    experiment_path = EVAL_DIR / "codex-terra-research-putnam-1976-a2.v0.1.json"
    experiment = _load(experiment_path.name)

    with agent_eval._prepared_experiment(
        experiment_path,
        experiment,
        prepare_installed_plugin=False,
        prepare_direct_runtime=True,
    ) as prepared:
        prepared_experiment = json.loads(prepared.read_text(encoding="utf-8"))
        arguments = prepared_experiment["driver"]["args"]
        command = Path(arguments[arguments.index("--target-server-command") + 1])
        cwd = Path(arguments[arguments.index("--target-server-cwd") + 1])
        assert command.is_file()
        assert cwd.is_dir()
        assert not command.is_relative_to(ROOT)
        assert not cwd.is_relative_to(ROOT)

    assert not command.exists()
    assert not cwd.exists()


def test_report_output_cannot_escape_the_gitignored_eval_directory(tmp_path: Path) -> None:
    inside = agent_eval.DEFAULT_OUTPUT_DIR / "nested" / "report.json"
    assert agent_eval._report_output(str(inside), "experiment") == inside.resolve()

    with pytest.raises(SystemExit, match="must stay under"):
        agent_eval._report_output(str(tmp_path / "outside.json"), "experiment")


def test_installed_skill_routes_machine_semantics_to_one_nested_run_call() -> None:
    skill = (ROOT / "plugins/math-anchor/skills/calculate/SKILL.md").read_text(encoding="utf-8")
    assert "MUST load and use it for fixed-width" in skill
    assert "fixed-width wrapping/saturating arithmetic" in skill
    assert "do not classify them as trivial arithmetic" in skill
    assert "outer envelope `{operation, arguments}`" in skill
    assert "never flatten them beside" in skill
    assert '"operation":"integer.machine_arithmetic"' in skill
    assert '"operation":"combinatorics.count"' in skill
    assert "never search or\ndescribe these shapes first" in skill
    assert '"overflowBehavior":"wrapping"' in skill
    assert '"action":"binomial"' in skill
