"""Honesty tests for the A4 equal-budget smoke harness.

Green tests here are evidence that the harness records the pre-registered
protocol. They are not completion of A4 research claims and not a benefit
percentage.
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research.ai_for_math_eval.arms import run_b0
from research.ai_for_math_eval.protocol import (
    ARM_B0,
    ARM_B1,
    ARM_B2,
    ARM_B2_MINUS,
    LIFECYCLE_CROSS_TASK,
    LIFECYCLE_VERIFIED,
    PROTOCOL_KIND,
    REPORT_KIND,
    TASK_CUBES,
    TASK_NEGATIVE,
    TASK_T1,
    load_protocol,
    protocol_digest,
)
from research.ai_for_math_eval.score import should_run_b2_minus
from research.ai_for_math_eval.smoke import run_smoke, write_report
from research.method_packs.format import PACK_ID
from research.polynomial_finite_sum_proposal.coverage import DIFFERENCE_IDENTITY_OBLIGATION_ID


RUNNER = ROOT / "research" / "ai_for_math_eval" / "run.py"


@pytest.fixture(scope="module")
def report() -> dict:
    return run_smoke()


def _cell(report: dict, arm: str, task: str) -> dict:
    for cell in report["cells"]:
        if cell["arm"] == arm and cell["task"] == task:
            return cell
    raise AssertionError(f"missing cell {arm}×{task}")


def test_protocol_is_pre_registered() -> None:
    protocol = load_protocol()
    assert protocol["kind"] == PROTOCOL_KIND
    assert protocol["preRegistered"] is True
    assert protocol["promotionForbiddenInThisSmoke"] is True
    assert protocol["notABenefitPercentage"] is True
    assert protocol["model"]["callsAllowed"] is False
    assert protocol["budget"]["dollarCosts"] is None
    ids = [task["id"] for task in protocol["tasks"]]
    assert ids == [TASK_T1, TASK_CUBES, TASK_NEGATIVE]
    by_id = {task["id"]: task for task in protocol["tasks"]}
    assert by_id[TASK_T1]["summand"] == "k^2"
    assert by_id[TASK_T1]["lower"] == 1
    assert by_id[TASK_T1]["upper"] == 10
    assert by_id[TASK_T1]["expectedExact"] == "385"
    assert by_id[TASK_CUBES]["summand"] == "k^3"
    assert by_id[TASK_CUBES]["lower"] == 1
    assert by_id[TASK_CUBES]["upper"] == 20
    assert by_id[TASK_CUBES]["expectedExact"] == "44100"
    assert by_id[TASK_NEGATIVE]["summand"] == "1/k"
    assert by_id[TASK_NEGATIVE]["countedAsSolved"] is False
    assert protocol["honesty"]["lifecycleEvidenceIsNotSemanticAdoption"] is True


def test_b0_and_b1_produce_t1_and_cubes_values(report: dict) -> None:
    b0_t1 = _cell(report, ARM_B0, TASK_T1)
    b1_t1 = _cell(report, ARM_B1, TASK_T1)
    b0_cubes = _cell(report, ARM_B0, TASK_CUBES)
    b1_cubes = _cell(report, ARM_B1, TASK_CUBES)
    assert b0_t1["summary"]["valueExact"] == "385"
    assert b1_t1["summary"]["valueExact"] == "385"
    assert b0_cubes["summary"]["valueExact"] == "44100"
    assert b1_cubes["summary"]["valueExact"] == "44100"
    assert b0_t1["scoring"]["countedAsSolved"] is True
    assert b1_t1["scoring"]["countedAsSolved"] is True
    assert b0_t1["summary"]["kind"] == "sympy_summation_baseline"
    assert b1_t1["summary"]["kind"] == "math-anchor.research.polynomial-finite-sum.v0"
    assert b1_t1["summary"]["baselineEmbedded"] is False
    assert b0_t1["coverage"]["generatedObligationIds"] == []
    assert b1_t1["coverage"]["generatedObligationIds"] == [DIFFERENCE_IDENTITY_OBLIGATION_ID]


def test_b2_cubes_reuse_path_is_not_semantic_adoption(report: dict) -> None:
    cell = _cell(report, ARM_B2, TASK_CUBES)
    assert cell["summary"]["valueExact"] == "44100"
    assert cell["summary"]["methodPackId"] == PACK_ID
    assert cell["scoring"]["reuseSignal"]["present"] is True
    assert cell["scoring"]["lifecycleEvidence"] == LIFECYCLE_CROSS_TASK
    assert cell["scoring"]["callAloneIsNotAdoption"] is True
    assert cell["scoring"]["semanticAdoption"] is False
    assert cell["scoring"]["coversOriginalTaskClaim"] is False
    steps = cell["summary"]["chainSteps"]
    assert steps[:3] == ["retrieve", "applicability", "instantiate"]
    assert "verify_difference_identity" in steps
    assert "combine_with_infrastructure_telescoping" in steps
    assert cell["summary"]["valueEnteredLaterStepsExact"] == "44100"
    assert cell["summary"]["adoption"]["extractionTaskIdNotReusedAsAnswer"] is True
    assert cell["summary"]["baselineEmbedded"] is False


def test_t1_b2_replay_does_not_mint_cross_task(report: dict) -> None:
    cell = _cell(report, ARM_B2, TASK_T1)
    assert cell["summary"]["valueExact"] == "385"
    assert cell["scoring"]["lifecycleEvidence"] == LIFECYCLE_VERIFIED
    assert cell["scoring"]["lifecycleEvidence"] != LIFECYCLE_CROSS_TASK
    assert cell["scoring"]["reuseSignal"]["present"] is False
    assert cell["scoring"]["semanticAdoption"] is False


def test_negative_harmonic_is_not_counted_as_solved(report: dict) -> None:
    for arm in (ARM_B0, ARM_B1, ARM_B2):
        cell = _cell(report, arm, TASK_NEGATIVE)
        assert cell["scoring"]["countedAsSolved"] is False
        assert cell["scoring"]["coversOriginalTaskClaim"] is False
        assert cell["scoring"]["propositionFalsified"] is False
        assert cell["scoring"]["unsupportedTreatedAsCounterexample"] is False
        assert cell["scoring"]["matchedPreRegisteredExpectation"] is True
    b0 = _cell(report, ARM_B0, TASK_NEGATIVE)
    assert b0["summary"]["status"] == "ok"
    assert b0["summary"]["valueExact"] == "11/6"
    assert b0["scoring"]["wrongAcceptance"] is False


def test_b1_b2_negative_fail_closed_not_proposition_false(report: dict) -> None:
    b1 = _cell(report, ARM_B1, TASK_NEGATIVE)
    b2 = _cell(report, ARM_B2, TASK_NEGATIVE)
    assert b1["summary"]["errorCode"] == "E_UNSUPPORTED"
    assert b2["summary"]["errorCode"] == "E_UNSUPPORTED"
    assert b2["summary"]["applicability"] == "rejected"
    assert b1["summary"]["valueExact"] is None
    assert b2["summary"]["valueExact"] is None
    assert b1["scoring"]["wrongAcceptance"] is False
    assert b2["scoring"]["wrongAcceptance"] is False
    assert b1["scoring"]["applicabilityMisjudgment"] is False
    assert b2["scoring"]["applicabilityMisjudgment"] is False
    assert b1["scoring"]["propositionFalsified"] is False
    assert b2["scoring"]["propositionFalsified"] is False


def test_covers_original_task_claim_stays_false(report: dict) -> None:
    for cell in report["cells"]:
        assert cell["scoring"]["coversOriginalTaskClaim"] is False
        assert cell["scoring"]["formalKernelChecked"] is False
        assert cell["coverage"]["coversOriginalTaskClaim"] is False
        assert cell["coverage"]["formalKernelChecked"] is False
    assert report["honesty"]["coversOriginalTaskClaimStaysFalse"] is True
    assert report["refusedClaims"]["coversOriginalTaskClaim"]["valueForced"] is False


def test_b2_minus_runs_because_reuse_signal_and_value_unchanged(report: dict) -> None:
    record = report["b2Minus"]
    assert record["ran"] is True
    assert record["packLoaded"] is False
    assert record["valueExact"] == "44100"
    assert record["b2ValueExact"] == "44100"
    assert record["valueUnchanged"] is True
    assert record["semanticAdoption"] is False
    minus = _cell(report, ARM_B2_MINUS, TASK_CUBES)
    assert minus["summary"]["valueExact"] == "44100"
    assert minus["summary"]["methodPackId"] is None
    assert minus["summary"]["kind"] == "math-anchor.research.polynomial-finite-sum.v0"
    assert minus["scoring"]["semanticAdoption"] is False


def test_b2_minus_skipped_when_no_reuse_signal() -> None:
    ran, reason = should_run_b2_minus(
        {"reuseSignal": {"present": False, "reason": "missing: retrieve_named_pack"}}
    )
    assert ran is False
    assert "skipped" in reason.lower()
    assert "retrieve_named_pack" in reason


def test_report_refuses_benefit_percent_and_dollar_costs(report: dict) -> None:
    assert report["kind"] == REPORT_KIND
    assert report["protocolDigest"] == protocol_digest()
    assert "overallBenefitPercent" not in report
    assert report["refusedClaims"]["overallBenefitPercent"]["emitted"] is False
    assert report["refusedClaims"]["dollarCosts"]["emitted"] is False
    assert report["budget"]["dollarCosts"] is None
    assert report["model"]["callsAllowed"] is False
    blob = json.dumps(report)
    assert "$" not in blob
    lowered = blob.lower()
    assert "usd" not in lowered
    assert report["honesty"]["smokeIsNotOverallBenefitPercent"] is True
    assert report["honesty"]["greenHarnessTestsAreNotA4Completion"] is True
    assert report["honesty"]["noDollarCostsInvented"] is True


def test_decision_is_not_promote(report: dict) -> None:
    decision = report["decision"]
    assert decision["promote"] is False
    assert decision["publicPromotion"] is False
    assert decision["keepExperimental"] is True
    assert decision["basedOnThisSmokeOnly"] is True
    assert decision["notAStatisticalSaving"] is True
    assert decision["verdict"] == "evidence_insufficient"
    assert decision["targetedFix"] is False
    assert "H1" in decision["next"]


def test_b0_does_not_load_method_pack() -> None:
    names = run_b0.__code__.co_names
    assert "apply_method_pack" not in names
    assert "load_pack" not in names
    source = (ROOT / "research" / "ai_for_math_eval" / "arms.py").read_text(encoding="utf-8")
    b0_block = source.split("def run_b1")[0]
    assert "apply_method_pack" not in b0_block
    assert "sympy_finite_sum" in b0_block


def test_equal_budget_b1_b2_do_not_embed_baseline(report: dict) -> None:
    for arm in (ARM_B1, ARM_B2):
        for task in (TASK_T1, TASK_CUBES):
            cell = _cell(report, arm, task)
            assert cell["summary"]["baselineEmbedded"] is False


def test_latency_cold_hot_recorded(report: dict) -> None:
    cell = _cell(report, ARM_B0, TASK_T1)
    assert "cold" in cell["latencyMs"]
    assert "hot" in cell["latencyMs"]
    assert cell["latencyMs"]["cold"] >= 0
    assert cell["latencyMs"]["hot"] >= 0


def test_cli_writes_report_and_refuses_overwrite(tmp_path: Path, report: dict) -> None:
    path = tmp_path / "a4-smoke-report.json"
    write_report(path, report)
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored["kind"] == REPORT_KIND
    assert stored["decision"]["promote"] is False
    with pytest.raises(Exception, match="refusing to overwrite"):
        write_report(path, report)


def test_cli_end_to_end(tmp_path: Path) -> None:
    output = tmp_path / "a4-smoke-report.json"
    completed = subprocess.run(
        [sys.executable, str(RUNNER), "--output", str(output)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert completed.returncode == 0, completed.stderr + completed.stdout
    stored = json.loads(output.read_text(encoding="utf-8"))
    assert stored["kind"] == REPORT_KIND
    assert stored["honesty"]["greenHarnessTestsAreNotA4Completion"] is True
    assert stored["b2Minus"]["ran"] is True
    stdout = json.loads(completed.stdout)
    assert stdout["decision"]["verdict"] == "evidence_insufficient"
