"""Regressions for the A2 experimental method pack.

Research proposal tests. Not evidence that the pack is a public Capability.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research.method_packs.apply import PackApplicationError, apply_method_pack
from research.method_packs.extract import IN_SCOPE_CASES, extract_from_t1
from research.method_packs.format import (
    EXTRACTION_TASK_ID,
    HELD_OUT_SECOND_TASK_ID,
    LIFECYCLE_CANDIDATE,
    LIFECYCLE_CROSS_TASK,
    LIFECYCLE_VERIFIED,
    NOVELTY_KNOWN_ADAPTATION,
    PACK_ID,
)
from research.method_packs.loader import PackFormatError, load_pack, validate_pack
from research.polynomial_finite_sum_proposal.polynomials import DomainError
from research.polynomial_finite_sum_proposal.runner import run_polynomial_finite_sum
from research.polynomial_finite_sum_proposal.telescoping import (
    TELESCOPING_RULE_ID,
    TELESCOPING_RULE_ORIGIN,
)


RUNNER = ROOT / "research" / "method_packs" / "run.py"
EXAMPLES = ROOT / "research" / "method_packs" / "examples"
PACK_PATH = (
    ROOT
    / "research"
    / "method_packs"
    / "polynomial_antidifference_gosper.v0"
    / "pack.json"
)
A1_EXAMPLE = (
    ROOT
    / "research"
    / "polynomial_finite_sum_proposal"
    / "examples"
    / "sum-k-squared-1-to-10.json"
)
FORBIDDEN_CALL = re.compile(r"(?<![A-Za-z0-9_])(?:eval|exec|sympify|parse_expr)\s*\(")


def _cli(*args: str, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(RUNNER), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )


def test_frozen_pack_is_experimental_and_honest() -> None:
    pack = load_pack(PACK_PATH)
    assert pack["id"] == PACK_ID
    assert pack["status"] == LIFECYCLE_VERIFIED
    assert pack["publicPromotion"] is False
    assert pack["notAPublicCapability"] is True
    assert pack["novelty"]["status"] == NOVELTY_KNOWN_ADAPTATION
    assert pack["novelty"]["autoClaimed"] is False
    assert pack["verification"]["formalKernelChecked"] is False
    assert pack["infrastructureUsedNotExtracted"]["id"] == TELESCOPING_RULE_ID
    assert pack["infrastructureUsedNotExtracted"]["agentExtracted"] is False
    assert pack["infrastructureUsedNotExtracted"]["countsAsA2Novelty"] is False
    assert pack["provenance"]["extractionTaskId"] == "T1"
    assert pack["provenance"]["hiddenModelReasoningRequired"] is False
    encoded = json.dumps(pack)
    assert "formal_kernel_checked" not in encoded or pack["verification"]["formalKernelChecked"] is False
    assert "385" not in encoded
    assert "44100" not in encoded


def test_second_task_file_does_not_carry_t1_solution() -> None:
    task = json.loads((EXAMPLES / "sum-k-cubed-1-to-20.json").read_text(encoding="utf-8"))
    assert task["taskId"] == HELD_OUT_SECOND_TASK_ID
    assert task["summand"] == "k^3"
    assert task["lower"] == 1
    assert task["upper"] == 20
    assert "antidifference" not in task
    blob = json.dumps(task)
    assert "385" not in blob
    t1 = json.loads(A1_EXAMPLE.read_text(encoding="utf-8"))
    assert t1["summand"] == "k^2"
    assert t1["upper"] == 10


def test_second_task_sum_of_cubes_reuses_pack() -> None:
    task = json.loads((EXAMPLES / "sum-k-cubed-1-to-20.json").read_text(encoding="utf-8"))
    result = apply_method_pack(task)
    assert result["status"] == "ok"
    assert result["value"]["exact"] == "44100"
    assert result["formalKernelChecked"] is False
    assert result["methodPack"]["id"] == PACK_ID
    assert result["methodPack"]["novelty"] == NOVELTY_KNOWN_ADAPTATION
    assert result["params"]["summand"] == "k^3"
    assert result["params"]["antidifferenceSupplied"] is False
    assert result["adoption"]["used"] is True
    assert result["adoption"]["lifecycleEvidence"] == LIFECYCLE_CROSS_TASK
    assert result["adoption"]["extractionTaskIdNotReusedAsAnswer"] is True
    assert result["downstream"]["ruleId"] == TELESCOPING_RULE_ID
    assert result["downstream"]["agentExtracted"] is False
    assert result["downstream"]["value"]["exact"] == "44100"
    assert result["baseline"]["agrees"] is True
    steps = [item["step"] for item in result["chain"]]
    assert steps == [
        "retrieve",
        "applicability",
        "instantiate",
        "construct_antidifference",
        "verify_difference_identity",
        "combine_with_infrastructure_telescoping",
    ]
    assert result["chain"][0]["methodId"] == PACK_ID
    assert result["chain"][2]["sourceSolutionCarried"] is False
    assert result["chain"][2]["untrustedCode"] is False
    assert result["verification"]["status"] == "checked"
    assert result["verification"]["formalKernelChecked"] is False
    assert result["verification"]["assuranceLevel"] == "exact_symbolic"
    assert "385" not in json.dumps(result["params"])
    assert "formal_kernel_checked" not in json.dumps(result) or result["formalKernelChecked"] is False


def test_t1_replay_does_not_mint_cross_task_lifecycle() -> None:
    replay = apply_method_pack({"summand": "k^2", "lower": 1, "upper": 10})
    assert replay["status"] == "ok"
    assert replay["value"]["exact"] == "385"
    assert replay["adoption"]["used"] is True
    assert replay["adoption"]["lifecycleEvidence"] == LIFECYCLE_VERIFIED
    assert replay["adoption"]["lifecycleEvidence"] != LIFECYCLE_CROSS_TASK
    assert replay["adoption"]["extractionTaskIdNotReusedAsAnswer"] is False
    assert replay["chain"][2]["sourceSolutionCarried"] is False

    labeled = apply_method_pack(
        {
            "taskId": EXTRACTION_TASK_ID,
            "summand": "k^2",
            "lower": 1,
            "upper": 10,
        }
    )
    assert labeled["adoption"]["lifecycleEvidence"] != LIFECYCLE_CROSS_TASK
    assert labeled["adoption"]["extractionTaskIdNotReusedAsAnswer"] is False

    equivalent = apply_method_pack(
        {
            "taskId": "alias-not-extraction-id",
            "summand": "k**2",
            "lower": 1,
            "upper": 10,
        }
    )
    assert equivalent["status"] == "ok"
    assert equivalent["value"]["exact"] == "385"
    assert equivalent["adoption"]["lifecycleEvidence"] != LIFECYCLE_CROSS_TASK
    assert equivalent["adoption"]["extractionTaskIdNotReusedAsAnswer"] is False


def test_missing_task_id_is_not_a_reuse_claim() -> None:
    result = apply_method_pack({"summand": "k^3", "lower": 1, "upper": 20})
    assert result["status"] == "ok"
    assert result["adoption"]["lifecycleEvidence"] == LIFECYCLE_CROSS_TASK
    assert result["adoption"]["extractionTaskIdNotReusedAsAnswer"] is False


def test_wrong_antidifference_on_second_task_is_falsified() -> None:
    result = apply_method_pack(
        {
            "taskId": HELD_OUT_SECOND_TASK_ID,
            "summand": "k^3",
            "lower": 1,
            "upper": 20,
            "antidifference": "k^4 / 4",
            "compareBaseline": False,
        }
    )
    assert result["status"] == "falsified"
    assert "value" not in result
    assert "downstream" not in result
    assert result["formalKernelChecked"] is False
    assert result["verification"]["status"] == "falsified"
    assert result["chain"][-1]["step"] == "verify_difference_identity"
    assert result["chain"][2]["sourceSolutionCarried"] is True
    assert result["adoption"]["lifecycleEvidence"] != LIFECYCLE_CROSS_TASK


def test_reversed_bounds_are_inapplicable() -> None:
    with pytest.raises(PackApplicationError, match="reversed bounds") as caught:
        apply_method_pack({"summand": "k^3", "lower": 5, "upper": 1})
    assert caught.value.code == "E_DOMAIN"
    assert caught.value.details["applicability"] == "rejected"


def test_inapplicable_harmonic_is_rejected() -> None:
    task = json.loads((EXAMPLES / "inapplicable-1-over-k.json").read_text(encoding="utf-8"))
    with pytest.raises(PackApplicationError, match="constant denominators") as caught:
        apply_method_pack(task)
    assert caught.value.code == "E_UNSUPPORTED"
    assert caught.value.details["applicability"] == "rejected"
    assert caught.value.details["methodPackId"] == PACK_ID


def test_a1_sum_of_squares_still_works() -> None:
    result = run_polynomial_finite_sum(summand="k^2", lower=1, upper=10)
    assert result["status"] == "ok"
    assert result["value"]["exact"] == "385"
    assert result["identity"]["status"] == "checked"
    assert result["formalKernelChecked"] is False
    assert result["combinationRule"]["origin"] == TELESCOPING_RULE_ORIGIN
    assert result["combinationRule"]["agentExtracted"] is False


def test_extraction_holds_out_second_task_and_verifies_scope(tmp_path: Path) -> None:
    assert all("k^3" not in case["summand"] for case in IN_SCOPE_CASES)
    assert all(case["id"] != HELD_OUT_SECOND_TASK_ID for case in IN_SCOPE_CASES)
    evidence = extract_from_t1(output_dir=tmp_path)
    assert evidence["candidate"]["novelty"]["status"] == NOVELTY_KNOWN_ADAPTATION
    assert evidence["candidate"]["notExtracted"]["agentExtracted"] is False
    assert evidence["inScopeVerification"]["allPassed"] is True
    assert evidence["inScopeVerification"]["heldOutExcluded"] is True
    assert evidence["domainAndNegatives"]["allRejected"] is True
    assert evidence["lifecycle"]["verifiedInDeclaredScope"]["status"] == LIFECYCLE_VERIFIED
    assert evidence["lifecycle"]["crossTaskUseEvidence"]["status"] == "not_recorded_by_extraction"
    assert evidence["t1SourceArtifact"]["value"]["exact"] == "385"
    assert (tmp_path / "dedup.json").is_file()


def test_candidate_pack_is_not_executable() -> None:
    pack = json.loads(PACK_PATH.read_text(encoding="utf-8"))
    pack["status"] = LIFECYCLE_CANDIDATE
    validate_pack(pack)
    with pytest.raises(PackFormatError, match="not executable"):
        apply_method_pack(
            {"summand": "k^3", "lower": 1, "upper": 20, "taskId": HELD_OUT_SECOND_TASK_ID},
            pack=pack,
        )


def test_unknown_instantiation_rule_is_rejected() -> None:
    pack = json.loads(PACK_PATH.read_text(encoding="utf-8"))
    pack["useInterface"]["instantiationRules"].append({"id": "eval_caller_python"})
    with pytest.raises(PackFormatError, match="allow-list"):
        validate_pack(pack)


def test_executable_keys_are_rejected_in_pack_json() -> None:
    pack = json.loads(PACK_PATH.read_text(encoding="utf-8"))
    pack["useInterface"]["eval"] = "p**2"
    with pytest.raises(PackFormatError, match="executable key"):
        validate_pack(pack)


def test_hockey_stick_after_explicit_rewrite_stays_conditional() -> None:
    task = json.loads((EXAMPLES / "hockey-stick-c-k-2-rewritten.json").read_text(encoding="utf-8"))
    result = apply_method_pack(task)
    assert result["status"] == "ok"
    assert result["value"]["exact"] == "165"
    assert result["conditionalPremises"][0]["status"] == "conditional"
    assert result["conditionalPremises"][0]["verifiedByPack"] is False
    assert result["params"]["summand"] == "k*(k-1)/2"
    assert result["adoption"]["lifecycleEvidence"] == LIFECYCLE_CROSS_TASK
    assert result["adoption"]["extractionTaskIdNotReusedAsAnswer"] is True


def test_self_certified_premise_is_rejected() -> None:
    with pytest.raises(PackApplicationError, match="verifiedByPack"):
        apply_method_pack(
            {
                "summand": "k*(k-1)/2",
                "lower": 2,
                "upper": 10,
                "premises": [
                    {
                        "id": "forged",
                        "statement": "C(k,2)=k*(k-1)/2",
                        "verifiedByPack": True,
                    }
                ],
            }
        )


def test_runtime_domain_error_is_not_inapplicable(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fail(**_kwargs: object) -> dict[str, object]:
        raise DomainError(
            "E_RUNTIME",
            "checked telescoping value disagrees with the SymPy summation baseline",
        )

    monkeypatch.setattr("research.method_packs.apply.run_polynomial_finite_sum", fail)
    with pytest.raises(PackApplicationError, match="baseline") as caught:
        apply_method_pack({"summand": "k^3", "lower": 1, "upper": 20})
    assert caught.value.code == "E_RUNTIME"
    assert caught.value.details.get("applicability") != "rejected"
    assert caught.value.details.get("reason") == "runtime_inconsistency"

    from research.method_packs.run import main

    assert main(["apply", "--task", str(EXAMPLES / "sum-k-cubed-1-to-20.json")]) == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "error"
    assert payload["error"]["code"] == "E_RUNTIME"


def test_method_pack_python_does_not_call_dynamic_evaluators() -> None:
    root = ROOT / "research" / "method_packs"
    violations = []
    for path in sorted(root.rglob("*.py")):
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if FORBIDDEN_CALL.search(line):
                violations.append(f"{path.relative_to(ROOT)}:{line_number}: {line.strip()}")
    assert violations == []


def test_cli_second_task_rejection_and_a1_example(tmp_path: Path) -> None:
    output = tmp_path / "sum.json"
    chain = tmp_path / "chain.json"
    adoption = tmp_path / "adoption.json"
    completed = _cli(
        "apply",
        "--task",
        str(EXAMPLES / "sum-k-cubed-1-to-20.json"),
        "--output",
        str(output),
        "--chain-output",
        str(chain),
        "--adoption-output",
        str(adoption),
    )
    assert completed.returncode == 0, completed.stderr + completed.stdout
    result = json.loads(completed.stdout)
    assert result["value"]["exact"] == "44100"
    assert result["formalKernelChecked"] is False
    assert json.loads(output.read_text())["value"]["exact"] == "44100"
    stored_chain = json.loads(chain.read_text())
    assert stored_chain[-1]["step"] == "combine_with_infrastructure_telescoping"
    assert stored_chain[-1]["agentExtracted"] is False
    stored_adoption = json.loads(adoption.read_text())
    assert stored_adoption["used"] is True
    assert stored_adoption["lifecycleEvidence"] == LIFECYCLE_CROSS_TASK

    rejected = _cli("apply", "--task", str(EXAMPLES / "inapplicable-1-over-k.json"))
    assert rejected.returncode == 2
    payload = json.loads(rejected.stdout)
    assert payload["status"] == "inapplicable"
    assert payload["error"]["code"] == "E_UNSUPPORTED"
    assert payload["methodPack"]["id"] == PACK_ID

    a1_still = run_polynomial_finite_sum(summand="k^2", lower=1, upper=10)
    assert a1_still["value"]["exact"] == "385"
