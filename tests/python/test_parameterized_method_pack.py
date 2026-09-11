"""Regressions for the parameterized shifted-square method pack.

Research proposal tests. Not evidence that the pack is a public Capability.
The reuse path must instantiate saved G(k,c) without reconstructing via Gosper.
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research.method_packs.apply import PackApplicationError, apply_method_pack
from research.method_packs.format import (
    LIFECYCLE_CROSS_TASK,
    LIFECYCLE_VERIFIED,
    NOVELTY_KNOWN_ADAPTATION,
    PARAM_EXTRACTION_TASK_ID,
    PARAM_HELD_OUT_TASK_ID,
    PARAM_PACK_ID,
    PARAM_REQUIRED_INSTANTIATION_RULE_IDS,
)
from research.method_packs.loader import PackFormatError, load_pack, validate_pack
from research.method_packs.shifted_square import (
    CANONICAL_G_SOURCE,
    canonical_g_terms,
    instantiate_univariate,
    match_shifted_square,
    monomial_antidifference,
)
from research.method_packs.shifted_square_extract import extract_shifted_square
from research.polynomial_finite_sum_proposal.runner import run_polynomial_finite_sum
from research.polynomial_finite_sum_proposal.telescoping import TELESCOPING_RULE_ID


RUNNER = ROOT / "research" / "method_packs" / "run.py"
EXAMPLES = ROOT / "research" / "method_packs" / "examples"
PARAM_PACK_PATH = (
    ROOT
    / "research"
    / "method_packs"
    / "shifted_square_antidifference.v0"
    / "pack.json"
)
HELD_OUT = EXAMPLES / "shifted-square-held-out-c3-2-to-7.json"
EXTRACT_TASK = EXAMPLES / "shifted-square-extract-c1-0-to-4.json"


def _cli(*args: str, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(RUNNER), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )


def _pack() -> dict:
    return load_pack(PARAM_PACK_PATH)


def test_frozen_param_pack_carries_instantiable_g() -> None:
    pack = _pack()
    assert pack["id"] == PARAM_PACK_ID
    assert pack["status"] == LIFECYCLE_VERIFIED
    assert pack["publicPromotion"] is False
    assert pack["notAPublicCapability"] is True
    assert pack["novelty"]["status"] == NOVELTY_KNOWN_ADAPTATION
    assert pack["novelty"]["autoClaimed"] is False
    assert pack["verification"]["formalKernelChecked"] is False
    payload = pack["mathSemantics"]["parametricAntidifference"]
    assert payload["source"] == CANONICAL_G_SOURCE
    assert payload["notFromGosper"] is True
    assert pack["useInterface"]["reconstructionOnReusePath"] is False
    ids = tuple(rule["id"] for rule in pack["useInterface"]["instantiationRules"])
    assert ids == PARAM_REQUIRED_INSTANTIATION_RULE_IDS
    assert "construct_antidifference_sympy_gosper" not in ids
    encoded = json.dumps(pack)
    assert "355" not in encoded
    assert "44100" not in encoded
    assert "formal_kernel_checked" not in encoded or pack["verification"]["formalKernelChecked"] is False


def test_derived_g_matches_canonical_source() -> None:
    terms = canonical_g_terms()
    from fractions import Fraction

    assert monomial_antidifference(0) == {1: Fraction(1)}
    assert monomial_antidifference(1) == {2: Fraction(1, 2), 1: Fraction(-1, 2)}
    assert monomial_antidifference(2) == {
        3: Fraction(1, 3),
        2: Fraction(-1, 2),
        1: Fraction(1, 6),
    }
    instantiated = instantiate_univariate(terms, Fraction(1))
    assert instantiated[3] == Fraction(1, 3)


def test_held_out_instantiates_saved_g_without_gosper() -> None:
    task = json.loads(HELD_OUT.read_text(encoding="utf-8"))
    assert task["taskId"] == PARAM_HELD_OUT_TASK_ID
    assert task["parameterC"] == "3"
    result = apply_method_pack(task, pack=_pack(), compare_baseline=True)
    assert result["status"] == "ok"
    assert result["value"]["exact"] == "355"
    assert result["constructor"] == "instantiated-saved-parametric-antidifference"
    assert result["reconstructionDisabled"] is True
    assert result["gosperCalled"] is False
    assert result["formalKernelChecked"] is False
    assert result["generalIdentity"]["status"] == "checked"
    assert result["identity"]["status"] == "checked"
    assert "k" in result["identity"]["right"]
    assert result["adoption"]["used"] is True
    assert result["adoption"]["lifecycleEvidence"] == LIFECYCLE_CROSS_TASK
    assert result["adoption"]["extractionTaskIdNotReusedAsAnswer"] is True
    assert result["downstream"]["ruleId"] == TELESCOPING_RULE_ID
    assert result["downstream"]["agentExtracted"] is False
    assert result["baseline"]["agrees"] is True
    steps = [item["step"] for item in result["chain"]]
    assert steps == [
        "retrieve",
        "applicability",
        "instantiate",
        "verify_general_difference_identity",
        "verify_difference_identity",
        "combine_with_infrastructure_telescoping",
    ]
    assert result["chain"][2]["reconstructionDisabled"] is True
    assert result["chain"][2]["gosperCalled"] is False
    assert "gosper" not in result["constructor"].lower()


def test_reuse_path_does_not_call_gosper_or_construct(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("reconstruction must stay disabled on the parameterized reuse path")

    monkeypatch.setattr("sympy.concrete.gosper.gosper_sum", boom)
    monkeypatch.setattr(
        "research.polynomial_finite_sum_proposal.polynomials.construct_antidifference",
        boom,
    )
    task = json.loads(HELD_OUT.read_text(encoding="utf-8"))
    result = apply_method_pack(task, pack=_pack(), compare_baseline=False)
    assert result["status"] == "ok"
    assert result["value"]["exact"] == "355"
    assert result["gosperCalled"] is False


def test_apply_modules_do_not_import_gosper() -> None:
    import ast

    from research.method_packs import shifted_square, shifted_square_apply

    forbidden = {"gosper_sum", "construct_antidifference"}
    for module in (shifted_square, shifted_square_apply):
        tree = ast.parse(inspect.getsource(module))
        names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                names.update(alias.name for alias in node.names)
            elif isinstance(node, ast.Attribute):
                names.add(node.attr)
            elif isinstance(node, ast.Name):
                names.add(node.id)
        assert names.isdisjoint(forbidden)


def test_stripped_payload_cannot_complete_reuse_path() -> None:
    pack = json.loads(PARAM_PACK_PATH.read_text(encoding="utf-8"))
    del pack["mathSemantics"]["parametricAntidifference"]
    with pytest.raises(PackFormatError, match="parametricAntidifference"):
        apply_method_pack(
            json.loads(HELD_OUT.read_text(encoding="utf-8")),
            pack=pack,
            compare_baseline=False,
        )


def test_wrong_saved_g_fails_closed_without_reconstructing() -> None:
    pack = json.loads(PARAM_PACK_PATH.read_text(encoding="utf-8"))
    pack["mathSemantics"]["parametricAntidifference"]["source"] = "k"
    result = apply_method_pack(
        json.loads(HELD_OUT.read_text(encoding="utf-8")),
        pack=pack,
        compare_baseline=False,
    )
    assert result["status"] != "ok"
    assert "value" not in result
    assert result["gosperCalled"] is False
    assert result["reconstructionDisabled"] is True


def test_fair_b1_baseline_may_still_construct() -> None:
    result = run_polynomial_finite_sum(
        summand="(k+3)^2",
        lower=2,
        upper=7,
        compare_baseline=True,
    )
    assert result["status"] == "ok"
    assert result["value"]["exact"] == "355"
    assert "gosper" in result["constructor"] or "summation" in result["constructor"]
    assert result["constructor"] != "instantiated-saved-parametric-antidifference"


def test_rational_held_out_and_extraction_replay() -> None:
    half = json.loads(
        (EXAMPLES / "shifted-square-held-out-c-half-1-to-3.json").read_text(encoding="utf-8")
    )
    result = apply_method_pack(half, pack=_pack(), compare_baseline=True)
    assert result["status"] == "ok"
    assert result["value"]["exact"] == "83/4"
    assert result["params"]["parameterC"] == "1/2"
    assert result["adoption"]["lifecycleEvidence"] == LIFECYCLE_CROSS_TASK

    extraction = json.loads(EXTRACT_TASK.read_text(encoding="utf-8"))
    replay = apply_method_pack(extraction, pack=_pack(), compare_baseline=False)
    assert replay["status"] == "ok"
    assert replay["value"]["exact"] == "55"
    assert replay["adoption"]["lifecycleEvidence"] == LIFECYCLE_VERIFIED
    assert replay["adoption"]["lifecycleEvidence"] != LIFECYCLE_CROSS_TASK
    assert replay["adoption"]["extractionTaskIdNotReusedAsAnswer"] is False


def test_wrong_template_and_harmonic_fail_closed() -> None:
    pack = _pack()
    with pytest.raises(PackApplicationError, match="shifted-square family") as cubes:
        apply_method_pack(
            json.loads((EXAMPLES / "shifted-square-inapplicable-k-cubed.json").read_text(encoding="utf-8")),
            pack=pack,
            compare_baseline=False,
        )
    assert cubes.value.code == "E_UNSUPPORTED"
    assert cubes.value.details["applicability"] == "rejected"

    with pytest.raises(PackApplicationError, match="perfect square") as not_square:
        apply_method_pack(
            json.loads(
                (EXAMPLES / "shifted-square-inapplicable-not-square.json").read_text(encoding="utf-8")
            ),
            pack=pack,
            compare_baseline=False,
        )
    assert not_square.value.code == "E_UNSUPPORTED"

    with pytest.raises(PackApplicationError) as harmonic:
        apply_method_pack(
            json.loads(
                (EXAMPLES / "shifted-square-inapplicable-harmonic.json").read_text(encoding="utf-8")
            ),
            pack=pack,
            compare_baseline=False,
        )
    assert harmonic.value.code == "E_UNSUPPORTED"
    assert harmonic.value.details["applicability"] == "rejected"


def test_reversed_bounds_and_parameter_mismatch_fail_closed() -> None:
    pack = _pack()
    with pytest.raises(PackApplicationError, match="reversed bounds") as reversed_bounds:
        apply_method_pack(
            {"summand": "(k+1)^2", "lower": 5, "upper": 1},
            pack=pack,
            compare_baseline=False,
        )
    assert reversed_bounds.value.code == "E_DOMAIN"
    assert reversed_bounds.value.details["applicability"] == "rejected"

    with pytest.raises(PackApplicationError, match="parameterC does not match") as mismatch:
        apply_method_pack(
            {"summand": "(k+1)^2", "parameterC": "2", "lower": 0, "upper": 4},
            pack=pack,
            compare_baseline=False,
        )
    assert mismatch.value.code == "E_DOMAIN"


def test_over_limit_and_noninteger_bounds_fail_closed() -> None:
    """Declared |a|,|b|<=10^6 and integer-only bounds must not NameError."""
    pack = _pack()
    with pytest.raises(PackApplicationError, match="magnitude may be at most") as over_limit:
        apply_method_pack(
            {"summand": "(k+3)^2", "parameterC": 3, "lower": 1000001, "upper": 1000002},
            pack=pack,
            compare_baseline=False,
        )
    assert over_limit.value.code == "E_LIMIT"
    assert over_limit.value.details["applicability"] == "rejected"
    assert over_limit.value.details["reason"] == "input_outside_declared_pack_domain"

    with pytest.raises(PackApplicationError, match="must be an integer") as non_int:
        apply_method_pack(
            {"summand": "(k+3)^2", "parameterC": 3, "lower": 1.5, "upper": 2},
            pack=pack,
            compare_baseline=False,
        )
    assert non_int.value.code == "E_DOMAIN"
    assert non_int.value.details["applicability"] == "rejected"

    with pytest.raises(PackApplicationError, match="must be an integer") as bool_bound:
        apply_method_pack(
            {"summand": "(k+3)^2", "parameterC": 3, "lower": True, "upper": 2},
            pack=pack,
            compare_baseline=False,
        )
    assert bool_bound.value.code == "E_DOMAIN"


def test_caller_antidifference_is_rejected() -> None:
    with pytest.raises(PackApplicationError, match="saved G"):
        apply_method_pack(
            {
                "summand": "(k+3)^2",
                "lower": 2,
                "upper": 7,
                "antidifference": "k**3",
            },
            pack=_pack(),
            compare_baseline=False,
        )


def test_gosper_pack_still_reconstructs_on_its_own_path() -> None:
    from research.method_packs.format import PACK_ID

    result = apply_method_pack({"summand": "k^3", "lower": 1, "upper": 20})
    assert result["status"] == "ok"
    assert result["value"]["exact"] == "44100"
    assert result["methodPack"]["id"] == PACK_ID
    assert "gosper" in result["constructor"] or result["params"]["antidifferenceSupplied"] is False


def test_extraction_holds_out_second_task(tmp_path: Path) -> None:
    evidence = extract_shifted_square(output_dir=tmp_path)
    assert evidence["candidate"]["novelty"]["status"] == NOVELTY_KNOWN_ADAPTATION
    assert evidence["inScopeVerification"]["allPassed"] is True
    assert evidence["inScopeVerification"]["heldOutExcluded"] is True
    assert evidence["domainAndNegatives"]["allRejected"] is True
    assert evidence["lifecycle"]["verifiedInDeclaredScope"]["status"] == LIFECYCLE_VERIFIED
    assert evidence["extractionTask"]["value"]["exact"] == "55"
    assert evidence["extractionTask"]["gosperCalled"] is False
    assert evidence["fairB1Baseline"]["agreesWithPackApply"] is True
    assert "gosper" in evidence["fairB1Baseline"]["constructor"]
    assert PARAM_HELD_OUT_TASK_ID not in json.dumps(evidence["inScopeVerification"]["cases"])
    assert "这个方法包相对不带包的 B1 流程" in evidence["whatThePackAddsVersusB1"]
    assert (tmp_path / "extraction_bundle.json").is_file()


def test_cli_held_out_and_rejection(tmp_path: Path) -> None:
    output = tmp_path / "held.json"
    chain = tmp_path / "chain.json"
    adoption = tmp_path / "adoption.json"
    completed = _cli(
        "apply",
        "--pack",
        str(PARAM_PACK_PATH),
        "--task",
        str(HELD_OUT),
        "--output",
        str(output),
        "--chain-output",
        str(chain),
        "--adoption-output",
        str(adoption),
        "--no-baseline",
    )
    assert completed.returncode == 0, completed.stderr + completed.stdout
    result = json.loads(completed.stdout)
    assert result["value"]["exact"] == "355"
    assert result["gosperCalled"] is False
    assert json.loads(output.read_text())["value"]["exact"] == "355"
    stored_chain = json.loads(chain.read_text())
    assert stored_chain[-1]["step"] == "combine_with_infrastructure_telescoping"
    assert json.loads(adoption.read_text())["lifecycleEvidence"] == LIFECYCLE_CROSS_TASK

    rejected = _cli(
        "apply",
        "--pack",
        str(PARAM_PACK_PATH),
        "--task",
        str(EXAMPLES / "shifted-square-inapplicable-k-cubed.json"),
    )
    assert rejected.returncode == 2
    payload = json.loads(rejected.stdout)
    assert payload["status"] == "inapplicable"
    assert payload["error"]["code"] == "E_UNSUPPORTED"
    assert payload["methodPack"]["id"] == PARAM_PACK_ID


def test_match_shifted_square_template() -> None:
    from fractions import Fraction

    assert match_shifted_square("(k+3)^2", "k") == Fraction(3)
    assert match_shifted_square("k^2", "k") == Fraction(0)
    with pytest.raises(Exception):
        match_shifted_square("k^3", "k")


def test_docs_keep_the_mandatory_sentence() -> None:
    sentence = (
        "这个方法包相对不带包的 B1 流程，额外保存了什么数学信息；未来哪一步工作可以因此不再重复？"
    )
    docs = (
        ROOT / "docs" / "research" / "ai-for-math" / "parameterized-method.md"
    ).read_text(encoding="utf-8")
    note = (
        ROOT
        / "research"
        / "method_packs"
        / "shifted_square_antidifference.v0"
        / "human_note.md"
    ).read_text(encoding="utf-8")
    assert sentence in docs
    assert sentence in note
    assert "不必再" in docs and "Gosper" in docs
