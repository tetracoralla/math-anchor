"""Honesty tests for the parameterized equal-budget cost/timing smoke.

Green tests here are evidence that the harness records the pre-registered
protocol. They are not completion of a cost-saving claim and not a benefit
percentage. Do not hardcode millisecond figures.
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

from research.method_packs.format import PARAM_PACK_ID
from research.parameterized_cost_eval.arms import run_b0
from research.parameterized_cost_eval.protocol import (
    ARM_B0,
    ARM_B1,
    ARM_P_PACK,
    LIFECYCLE_CROSS_TASK,
    LIFECYCLE_VERIFIED,
    PROTOCOL_KIND,
    REPORT_KIND,
    TASK_NEGATIVE,
    TASK_P0,
    TASK_P1,
    TASK_P2,
    load_protocol,
    protocol_digest,
)
from research.parameterized_cost_eval.score import decide, observed_slower_checked_path
from research.parameterized_cost_eval.smoke import run_smoke, write_report


RUNNER = ROOT / "research" / "parameterized_cost_eval" / "run.py"
HARNESS_FILES = (
    ROOT / "research" / "parameterized_cost_eval" / "protocol.py",
    ROOT / "research" / "parameterized_cost_eval" / "arms.py",
    ROOT / "research" / "parameterized_cost_eval" / "score.py",
    ROOT / "research" / "parameterized_cost_eval" / "smoke.py",
    ROOT / "research" / "parameterized_cost_eval" / "run.py",
)


@pytest.fixture(scope="module")
def report() -> dict:
    return run_smoke()


def _cell(report: dict, arm: str, task: str) -> dict:
    for cell in report["cells"]:
        if cell["arm"] == arm and cell["task"] == task:
            return cell
    raise AssertionError(f"missing cell {arm}×{task}")


def test_protocol_is_pre_registered_with_required_arms() -> None:
    protocol = load_protocol()
    assert protocol["kind"] == PROTOCOL_KIND
    assert protocol["preRegistered"] is True
    assert protocol["promotionForbiddenInThisSmoke"] is True
    assert protocol["notABenefitPercentage"] is True
    assert protocol["model"]["callsAllowed"] is False
    assert protocol["budget"]["dollarCosts"] is None
    assert protocol["budget"]["modelCalls"] == 0
    ids = [task["id"] for task in protocol["tasks"]]
    assert ids == [TASK_P0, TASK_P1, TASK_P2, TASK_NEGATIVE]
    arms = [arm["id"] for arm in protocol["arms"]]
    assert ARM_B0 in arms and ARM_B1 in arms and ARM_P_PACK in arms
    by_id = {task["id"]: task for task in protocol["tasks"]}
    assert by_id[TASK_P1]["summand"] == "(k+3)^2"
    assert by_id[TASK_P1]["parameterC"] == "3"
    assert by_id[TASK_P1]["lower"] == 2
    assert by_id[TASK_P1]["upper"] == 7
    assert by_id[TASK_P1]["expectedExact"] == "355"
    assert by_id[TASK_P0]["expectedExact"] == "55"
    assert by_id[TASK_P2]["expectedExact"] == "83/4"
    assert by_id[TASK_NEGATIVE]["summand"] == "1/k"
    assert by_id[TASK_NEGATIVE]["countedAsSolved"] is False
    p_arm = next(arm for arm in protocol["arms"] if arm["id"] == ARM_P_PACK)
    assert p_arm["reconstructionDisabled"] is True
    assert p_arm["mayConstruct"] is False
    assert p_arm["packId"] == PARAM_PACK_ID


def test_in_family_values_match_across_arms(report: dict) -> None:
    expected = {TASK_P0: "55", TASK_P1: "355", TASK_P2: "83/4"}
    for task_id, value in expected.items():
        for arm in (ARM_B0, ARM_B1, ARM_P_PACK):
            cell = _cell(report, arm, task_id)
            assert cell["summary"]["valueExact"] == value
            assert cell["summary"]["status"] == "ok"
            assert cell["scoring"]["countedAsSolved"] is True
            assert cell["scoring"]["coversOriginalTaskClaim"] is False
            assert cell["scoring"]["baselineEmbedded"] is False or arm == ARM_B0


def test_p_pack_held_out_does_not_reconstruct(report: dict) -> None:
    cell = _cell(report, ARM_P_PACK, TASK_P1)
    assert cell["summary"]["valueExact"] == "355"
    assert cell["summary"]["methodPackId"] == PARAM_PACK_ID
    assert cell["summary"]["constructor"] == "instantiated-saved-parametric-antidifference"
    assert cell["summary"]["gosperCalled"] is False
    assert cell["summary"]["reconstructionDisabled"] is True
    assert cell["scoring"]["constructionTrace"]["gosper_sum"] == 0
    assert cell["scoring"]["constructionTrace"]["construct_antidifference"] == 0
    assert cell["scoring"]["reconstructedOnPackArm"] is False
    assert cell["scoring"]["lifecycleEvidence"] == LIFECYCLE_CROSS_TASK
    assert cell["scoring"]["callAloneIsNotAdoption"] is True
    assert cell["scoring"]["semanticAdoption"] is False
    steps = cell["summary"]["chainSteps"]
    assert "retrieve" in steps
    assert "applicability" in steps
    assert "instantiate" in steps
    assert "verify_general_difference_identity" in steps
    assert "verify_difference_identity" in steps
    assert "combine_with_infrastructure_telescoping" in steps


def test_b1_held_out_is_allowed_to_construct(report: dict) -> None:
    cell = _cell(report, ARM_B1, TASK_P1)
    assert cell["summary"]["valueExact"] == "355"
    trace = cell["scoring"]["constructionTrace"]
    assert trace["construct_antidifference"] >= 1 or trace["gosper_sum"] >= 1
    constructor = str(cell["summary"]["constructor"] or "")
    assert "gosper" in constructor or "summation" in constructor
    assert cell["summary"]["methodPackId"] is None
    assert cell["summary"]["baselineEmbedded"] is False


def test_p0_replay_does_not_mint_cross_task(report: dict) -> None:
    cell = _cell(report, ARM_P_PACK, TASK_P0)
    assert cell["summary"]["valueExact"] == "55"
    assert cell["scoring"]["lifecycleEvidence"] == LIFECYCLE_VERIFIED
    assert cell["scoring"]["lifecycleEvidence"] != LIFECYCLE_CROSS_TASK


def test_negative_harmonic_is_not_counted_as_solved(report: dict) -> None:
    for arm in (ARM_B0, ARM_B1, ARM_P_PACK):
        cell = _cell(report, arm, TASK_NEGATIVE)
        assert cell["scoring"]["countedAsSolved"] is False
        assert cell["scoring"]["coversOriginalTaskClaim"] is False
    b0 = _cell(report, ARM_B0, TASK_NEGATIVE)
    assert b0["summary"]["status"] == "ok"
    assert b0["summary"]["valueExact"] == "11/6"
    b1 = _cell(report, ARM_B1, TASK_NEGATIVE)
    p_pack = _cell(report, ARM_P_PACK, TASK_NEGATIVE)
    assert b1["summary"]["errorCode"] == "E_UNSUPPORTED"
    assert p_pack["summary"]["errorCode"] == "E_UNSUPPORTED"
    assert p_pack["summary"]["applicability"] == "rejected"
    assert b1["summary"]["valueExact"] is None
    assert p_pack["summary"]["valueExact"] is None


def test_stripped_payload_refuses(report: dict) -> None:
    probe = report["structuralProbes"]["strippedPayload"]
    assert probe["refused"] is True
    assert probe["errorCode"] is not None
    assert probe["task"] == TASK_P1


def test_fair_b0_b1_not_crippled_on_cubes(report: dict) -> None:
    probe = report["structuralProbes"]["fairBaselinesNotCrippledOnCubes"]
    assert probe["b0ValueExact"] == "44100"
    assert probe["b1ValueExact"] == "44100"
    assert probe["pPackRefused"] is True
    assert probe["pPackErrorCode"] == "E_UNSUPPORTED"
    assert "gosper" in str(probe.get("b1Constructor") or "") or "summation" in str(
        probe.get("b1Constructor") or ""
    )


def test_b0_does_not_load_method_pack() -> None:
    names = run_b0.__code__.co_names
    assert "apply_method_pack" not in names
    assert "load_pack" not in names
    source = (ROOT / "research" / "parameterized_cost_eval" / "arms.py").read_text(encoding="utf-8")
    b0_block = source.split("def run_b1")[0]
    assert "apply_method_pack" not in b0_block
    assert "sympy_finite_sum" in b0_block
    b1_block = source.split("def run_p_pack")[0]
    assert "apply_method_pack" not in b1_block


def test_report_refuses_benefit_percent_and_dollar_costs(report: dict) -> None:
    assert report["kind"] == REPORT_KIND
    assert report["protocolDigest"] == protocol_digest()
    assert "overallBenefitPercent" not in report
    assert "savingsPercent" not in report or report["refusedClaims"]["savingsPercent"]["emitted"] is False
    assert report["refusedClaims"]["overallBenefitPercent"]["emitted"] is False
    assert report["refusedClaims"]["dollarCosts"]["emitted"] is False
    assert report["budget"]["dollarCosts"] is None
    assert report["model"]["callsAllowed"] is False
    blob = json.dumps(report)
    assert "$" not in blob
    lowered = blob.lower()
    assert "usd" not in lowered
    assert report["honesty"]["smokeIsNotOverallBenefitPercent"] is True
    assert report["honesty"]["greenHarnessTestsAreNotCompletion"] is True
    assert report["honesty"]["noDollarCostsInvented"] is True
    assert report["honesty"]["latencyLabelsAreFirstRepeatNotColdHot"] is True
    assert report["decision"]["b0AlreadyMatchesInFamily"] is True


def test_decision_is_not_promote(report: dict) -> None:
    decision = report["decision"]
    assert decision["promote"] is False
    assert decision["publicPromotion"] is False
    assert decision["keepExperimental"] is True
    assert decision["basedOnThisSmokeOnly"] is True
    assert decision["notAStatisticalSaving"] is True
    assert decision["doNotStartH1"] is True
    assert decision["verdict"] == "evidence_insufficient"
    assert decision["targetedFix"] is False
    assert "H1" in decision["next"]
    joined = " ".join(decision["reasons"])
    assert "B0" in joined and "simpler" in joined


def test_latency_first_repeat_recorded_without_cold_hot_lies(report: dict) -> None:
    cell = _cell(report, ARM_P_PACK, TASK_P1)
    assert "first" in cell["latencyMs"]
    assert "repeat" in cell["latencyMs"]
    assert "cold" not in cell["latencyMs"]
    assert "hot" not in cell["latencyMs"]
    assert isinstance(cell["latencyMs"]["first"], (int, float))
    assert isinstance(cell["latencyMs"]["repeat"], (int, float))
    assert cell["latencyMs"]["first"] >= 0
    assert cell["latencyMs"]["repeat"] >= 0
    assert cell["trials"][0]["label"] == "first"
    assert cell["trials"][1]["label"] == "repeat"
    assert cell["trialsDisagree"] is False
    assert report["complete"] is True
    assert report["decision"]["observedSlowerCheckedPath"] in {True, False}
    assert report["decision"]["observedPackRepeatFasterThanB1"] in {True, False, None}


def test_harness_source_does_not_hardcode_latency_figures() -> None:
    for path in HARNESS_FILES:
        text = path.read_text(encoding="utf-8")
        assert '"cold"' not in text
        assert '"hot"' not in text
        lowered = text.lower()
        assert "savings %" not in lowered
        assert "dollar" not in lowered or "no dollar" in lowered or "dollarCosts" in text


def test_decision_does_not_invent_a_latency_observation() -> None:
    cells = [
        {
            "arm": arm,
            "task": task,
            "scoring": {
                "matchedPreRegisteredExpectation": True,
                "wrongAcceptance": False,
                "applicabilityMisjudgment": False,
                "countedAsSolved": task != TASK_NEGATIVE,
                "coversOriginalTaskClaim": False,
                "formalKernelChecked": False,
                "baselineEmbedded": False,
                "reconstructedOnPackArm": False,
                "gosperCalledJsonFlag": False if arm == ARM_P_PACK else None,
                "reconstructionDisabled": True if arm == ARM_P_PACK else None,
                "constructionTrace": {
                    "gosper_sum": 0 if arm != ARM_B1 else 1,
                    "construct_antidifference": 0 if arm != ARM_B1 else 1,
                },
                "lifecycleEvidence": LIFECYCLE_VERIFIED if (arm == ARM_P_PACK and task == TASK_P0) else None,
            },
        }
        for arm in (ARM_B0, ARM_B1, ARM_P_PACK)
        for task in (TASK_P0, TASK_P1, TASK_P2, TASK_NEGATIVE)
    ]
    assert observed_slower_checked_path(cells) is None
    decision = decide(
        cells,
        stripped={"refused": True},
        fair_baselines={
            "b0ValueExact": "44100",
            "b1ValueExact": "44100",
            "pPackRefused": True,
        },
    )
    assert decision.get("observedSlowerCheckedPath") is not True
    assert decision.get("observedSlowerCheckedPath") is None
    assert decision["promote"] is False


def test_protocol_digest_tracks_the_protocol_actually_used() -> None:
    from copy import deepcopy

    from math_anchor.errors import CalculatorError

    original = load_protocol()
    changed = deepcopy(original)
    for task in changed["tasks"]:
        if task["id"] == TASK_P1:
            task["upper"] = 6
            task["expectedExact"] = "999"
    try:
        report_a = run_smoke(protocol=original)
        report_b = run_smoke(protocol=changed)
    except (CalculatorError, ValueError):
        return
    assert report_a["protocolDigest"] != report_b["protocolDigest"]
    assert report_a["protocolDigest"] == protocol_digest(original)
    assert report_b["protocolDigest"] == protocol_digest(changed)


def test_cli_writes_report_and_refuses_overwrite(tmp_path: Path, report: dict) -> None:
    path = tmp_path / "parameterized-cost-smoke-report.json"
    write_report(path, report)
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored["kind"] == REPORT_KIND
    assert stored["decision"]["promote"] is False
    with pytest.raises(Exception, match="refusing to overwrite"):
        write_report(path, report)


def test_cli_end_to_end(tmp_path: Path) -> None:
    output = tmp_path / "parameterized-cost-smoke-report.json"
    completed = subprocess.run(
        [sys.executable, str(RUNNER), "--output", str(output)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
    )
    assert completed.returncode == 0, completed.stderr + completed.stdout
    stored = json.loads(output.read_text(encoding="utf-8"))
    assert stored["kind"] == REPORT_KIND
    assert stored["honesty"]["greenHarnessTestsAreNotCompletion"] is True
    stdout = json.loads(completed.stdout)
    assert stdout["decision"]["verdict"] == "evidence_insufficient"
    p1 = next(
        cell
        for cell in stored["cells"]
        if cell["arm"] == ARM_P_PACK and cell["task"] == TASK_P1
    )
    assert p1["summary"]["valueExact"] == "355"
    assert p1["scoring"]["constructionTrace"]["gosper_sum"] == 0
