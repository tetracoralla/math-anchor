"""Honesty tests for the reuse-benefit smoke with strong CAS baselines.

Green tests here are evidence that the harness records the pre-registered
protocol and keeps three judgments separate. They are not completion of a
cost-saving claim and not a benefit percentage. Do not hardcode millisecond
figures.
"""

from __future__ import annotations

from copy import deepcopy
import ast
import inspect
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from math_anchor.errors import CalculatorError
from research.method_packs.format import PARAM_PACK_ID
from research.reuse_benefit_eval.arms import run_b0, run_b_codegen, run_b_template
from research.reuse_benefit_eval.protocol import (
    ARM_B0,
    ARM_B1,
    ARM_B_CODEGEN,
    ARM_B_TEMPLATE,
    ARM_P_PACK,
    HELD_OUT_TASKS,
    IN_FAMILY_TASKS,
    LIFECYCLE_CROSS_TASK,
    LIFECYCLE_VERIFIED,
    PRIMARY_ARMS,
    PROTOCOL_KIND,
    REPORT_KIND,
    TASK_NEGATIVE,
    TASK_P0,
    TASK_P1,
    TASK_P2,
    TASK_P3,
    TASK_P4,
    TASK_REVERSED,
    load_protocol,
    protocol_digest,
    validate_protocol,
)
from research.reuse_benefit_eval.score import decide, observed_slower_checked_path
from research.reuse_benefit_eval.smoke import run_smoke, write_report


RUNNER = ROOT / "research" / "reuse_benefit_eval" / "run.py"
HARNESS_FILES = (
    ROOT / "research" / "reuse_benefit_eval" / "protocol.py",
    ROOT / "research" / "reuse_benefit_eval" / "arms.py",
    ROOT / "research" / "reuse_benefit_eval" / "template.py",
    ROOT / "research" / "reuse_benefit_eval" / "codegen.py",
    ROOT / "research" / "reuse_benefit_eval" / "score.py",
    ROOT / "research" / "reuse_benefit_eval" / "smoke.py",
    ROOT / "research" / "reuse_benefit_eval" / "run.py",
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
    assert protocol["judgmentsAreSeparate"] is True
    assert protocol["model"]["callsAllowed"] is False
    assert protocol["budget"]["dollarCosts"] is None
    assert protocol["budget"]["modelCalls"] == 0
    ids = [task["id"] for task in protocol["tasks"]]
    assert ids == [
        TASK_P0,
        TASK_P1,
        TASK_P2,
        TASK_P3,
        TASK_P4,
        TASK_NEGATIVE,
        TASK_REVERSED,
    ]
    arms = [arm["id"] for arm in protocol["arms"]]
    assert tuple(arms) == PRIMARY_ARMS
    by_id = {task["id"]: task for task in protocol["tasks"]}
    assert by_id[TASK_P1]["expectedExact"] == "355"
    assert by_id[TASK_P3]["summand"] == "(k-2)^2"
    assert by_id[TASK_P3]["expectedExact"] == "28"
    assert by_id[TASK_P4]["expectedExact"] == "0"
    assert by_id[TASK_REVERSED]["countedAsSolved"] is False
    p_arm = next(arm for arm in protocol["arms"] if arm["id"] == ARM_P_PACK)
    assert p_arm["reconstructionDisabled"] is True
    assert p_arm["mayConstruct"] is False
    assert p_arm["packId"] == PARAM_PACK_ID
    template_arm = next(arm for arm in protocol["arms"] if arm["id"] == ARM_B_TEMPLATE)
    assert template_arm["mayCache"] is True
    assert template_arm["karrReversedBoundsAccepted"] is True
    assert "相对强基线" in protocol["mandatoryClaimZh"]


def test_unsupported_protocol_overrides_are_rejected() -> None:
    original = load_protocol()
    only_b0 = deepcopy(original)
    only_b0["arms"] = [arm for arm in only_b0["arms"] if arm["id"] == ARM_B0]
    with pytest.raises(ValueError, match="pre-registered"):
        validate_protocol(only_b0)
    with pytest.raises(ValueError, match="pre-registered"):
        run_smoke(protocol=only_b0)

    three_trials = deepcopy(original)
    three_trials["latency"] = {**three_trials["latency"], "trials": 3}
    with pytest.raises(ValueError, match="pre-registered"):
        validate_protocol(three_trials)

    mutated_task = deepcopy(original)
    mutated_task["tasks"][1]["upper"] = 6
    with pytest.raises(ValueError, match="pre-registered"):
        validate_protocol(mutated_task)


def test_in_family_values_match_across_strong_baselines(report: dict) -> None:
    expected = {
        TASK_P0: "55",
        TASK_P1: "355",
        TASK_P2: "83/4",
        TASK_P3: "28",
        TASK_P4: "0",
    }
    for task_id, value in expected.items():
        for arm in PRIMARY_ARMS:
            cell = _cell(report, arm, task_id)
            assert cell["summary"]["valueExact"] == value, f"{arm}×{task_id}"
            assert cell["summary"]["status"] == "ok"
            assert cell["scoring"]["countedAsSolved"] is True
            assert cell["scoring"]["coversOriginalTaskClaim"] is False
            assert cell["summary"]["floatingApproximation"] is False
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
    assert cell["scoring"]["usedSavedContent"] is True
    assert cell["scoring"]["lifecycleEvidence"] == LIFECYCLE_CROSS_TASK
    assert cell["scoring"]["callAloneIsNotAdoption"] is True
    assert cell["scoring"]["semanticAdoption"] is False
    steps = cell["summary"]["stepsExecuted"]
    assert "retrieve" in steps
    assert "instantiate" in steps
    assert "verify_general_difference_identity" in steps
    assert "verify_difference_identity" in steps


def test_additional_held_out_negative_c_reuses_saved_g(report: dict) -> None:
    for task_id in HELD_OUT_TASKS:
        cell = _cell(report, ARM_P_PACK, task_id)
        assert cell["scoring"]["usedSavedContent"] is True
        assert cell["scoring"]["constructionTrace"]["gosper_sum"] == 0
        assert cell["scoring"]["lifecycleEvidence"] == LIFECYCLE_CROSS_TASK


def test_b1_held_out_is_allowed_to_construct(report: dict) -> None:
    cell = _cell(report, ARM_B1, TASK_P1)
    assert cell["summary"]["valueExact"] == "355"
    trace = cell["scoring"]["constructionTrace"]
    assert trace["construct_antidifference"] >= 1 or trace["gosper_sum"] >= 1
    constructor = str(cell["summary"]["constructor"] or "")
    assert "gosper" in constructor or "summation" in constructor
    assert cell["summary"]["methodPackId"] is None
    assert cell["summary"]["usedSavedContent"] is False


def test_template_and_codegen_reuse_cached_g_without_gosper(report: dict) -> None:
    for arm in (ARM_B_TEMPLATE, ARM_B_CODEGEN):
        cell = _cell(report, arm, TASK_P3)
        assert cell["summary"]["valueExact"] == "28"
        assert cell["scoring"]["usedSavedContent"] is True
        assert cell["scoring"]["constructionTrace"]["gosper_sum"] == 0
        assert cell["scoring"]["constructionTrace"]["construct_antidifference"] == 0
        assert cell["summary"]["floatingApproximation"] is False
        assert cell["summary"]["methodPackId"] is None
        assert "check_instance_identity" not in cell["scoring"]["stepsExecuted"]
        assert "verify_difference_identity" not in cell["scoring"]["stepsExecuted"]


def test_p0_replay_does_not_mint_cross_task(report: dict) -> None:
    cell = _cell(report, ARM_P_PACK, TASK_P0)
    assert cell["summary"]["valueExact"] == "55"
    assert cell["scoring"]["lifecycleEvidence"] == LIFECYCLE_VERIFIED
    assert cell["scoring"]["lifecycleEvidence"] != LIFECYCLE_CROSS_TASK


def test_negative_harmonic_is_not_counted_as_solved(report: dict) -> None:
    for arm in PRIMARY_ARMS:
        cell = _cell(report, arm, TASK_NEGATIVE)
        assert cell["scoring"]["countedAsSolved"] is False
    b0 = _cell(report, ARM_B0, TASK_NEGATIVE)
    assert b0["summary"]["status"] == "ok"
    assert b0["summary"]["valueExact"] == "11/6"
    for arm in (ARM_B1, ARM_B_TEMPLATE, ARM_B_CODEGEN, ARM_P_PACK):
        cell = _cell(report, arm, TASK_NEGATIVE)
        assert cell["summary"]["errorCode"] == "E_UNSUPPORTED"
        assert cell["summary"]["valueExact"] is None


def test_reversed_bounds_are_never_solved_and_baselines_are_not_crippled(report: dict) -> None:
    for arm in PRIMARY_ARMS:
        cell = _cell(report, arm, TASK_REVERSED)
        assert cell["scoring"]["countedAsSolved"] is False
    for arm in (ARM_B0, ARM_B_TEMPLATE, ARM_B_CODEGEN):
        cell = _cell(report, arm, TASK_REVERSED)
        assert cell["summary"]["status"] == "ok"
        assert cell["summary"]["valueExact"] == "-50"
    for arm in (ARM_B1, ARM_P_PACK):
        cell = _cell(report, arm, TASK_REVERSED)
        assert cell["summary"]["errorCode"] == "E_DOMAIN"
        assert cell["summary"]["valueExact"] is None


def test_stripped_payload_and_wrong_g_fail_closed(report: dict) -> None:
    stripped = report["structuralProbes"]["strippedPayload"]
    assert stripped["refused"] is True
    assert stripped["task"] == TASK_P1
    wrong = report["structuralProbes"]["wrongSavedG"]
    assert wrong["failClosed"] is True
    assert wrong["emittedValue"] is False


def test_fair_baselines_not_crippled_on_cubes(report: dict) -> None:
    probe = report["structuralProbes"]["fairBaselinesNotCrippledOnCubes"]
    assert probe["b0ValueExact"] == "44100"
    assert probe["b1ValueExact"] == "44100"
    assert probe["pPackRefused"] is True
    assert probe["templateRefused"] is True
    assert probe["codegenRefused"] is True
    assert probe["pPackErrorCode"] == "E_UNSUPPORTED"


def test_c_codegen_float_backend_is_skipped_not_faked(report: dict) -> None:
    skip = report["structuralProbes"]["codegenSkip"]
    c_backend = skip["sympy.utilities.codegen.C"]
    assert c_backend["used"] is False
    probe = c_backend["probe"]
    assert probe["available"] is True
    assert probe["emitsFloatingType"] is True
    pycode = skip["sympy.printing.pycode"]
    assert pycode["used"] is False
    assert "exec" in pycode["reason"].lower() or "float" in pycode["reason"].lower()


def test_b0_does_not_load_method_pack() -> None:
    names = run_b0.__code__.co_names
    assert "apply_method_pack" not in names
    assert "load_pack" not in names
    source = (ROOT / "research" / "reuse_benefit_eval" / "arms.py").read_text(encoding="utf-8")
    b0_block = source.split("def run_b1")[0]
    assert "apply_method_pack" not in b0_block
    assert "sympy_finite_sum" in b0_block


def test_template_and_codegen_do_not_apply_the_pack() -> None:
    for func in (run_b_template, run_b_codegen):
        names = func.__code__.co_names
        assert "apply_method_pack" not in names
        assert "check_obligation_set" not in names
    from research.reuse_benefit_eval import codegen, template

    for module in (template, codegen):
        tree = ast.parse(inspect.getsource(module))
        names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                names.add(node.id)
        assert "eval" not in names
        assert "exec" not in names
        assert "apply_method_pack" not in names
        assert "gosper_sum" not in names


def test_report_refuses_benefit_percent_and_dollar_costs(report: dict) -> None:
    assert report["kind"] == REPORT_KIND
    assert report["protocolDigest"] == protocol_digest()
    assert report["refusedClaims"]["overallBenefitPercent"]["emitted"] is False
    assert report["refusedClaims"]["dollarCosts"]["emitted"] is False
    assert report["refusedClaims"]["savingsPercent"]["emitted"] is False
    assert report["refusedClaims"]["uniquenessFromFasterThanColdGosper"]["emitted"] is False
    assert report["refusedClaims"]["collapsedSuccessFlag"]["emitted"] is False
    assert report["budget"]["dollarCosts"] is None
    assert report["model"]["callsAllowed"] is False
    blob = json.dumps(report)
    assert "$" not in blob
    assert "usd" not in blob.lower()
    assert report["honesty"]["judgmentsAreNotOneSuccessFlag"] is True
    assert report["honesty"]["fasterThanColdGosperIsNotUniqueness"] is True
    assert report["decision"]["b0AlreadyMatchesInFamily"] is True
    assert report["decision"]["bTemplateAlreadyMatchesP"] is True
    assert report["decision"]["bCodegenAlreadyMatchesP"] is True


def test_three_judgments_are_separate_and_not_one_success(report: dict) -> None:
    judgments = report["judgments"]
    assert judgments["notCollapsedIntoOneSuccess"] is True
    assert set(judgments) >= {"trustworthiness", "behavior", "utility", "notCollapsedIntoOneSuccess"}
    trust = judgments["trustworthiness"]
    behavior = judgments["behavior"]
    utility = judgments["utility"]
    assert trust["verdict"] == "holds_in_declared_domain"
    assert trust["notUtility"] is True
    assert trust["notBehavior"] is True
    assert behavior["verdict"] == "pack_uses_saved_content"
    assert behavior["notUtility"] is True
    assert behavior["packReuseIsNotUniqueVsTemplate"] is True
    assert utility["verdict"] == "no_net_benefit_vs_strong_baselines"
    assert utility["mayBeNegative"] is True
    assert utility["fasterThanColdGosperIsNotUniqueness"] is True
    assert utility["bTemplateAlreadyMatchesP"] is True
    assert report["decision"]["verdict"] == "evidence_insufficient"
    assert report["decision"]["promote"] is False
    assert "success" not in report["decision"] or report["decision"].get("success") is not True


def test_decision_is_not_promote(report: dict) -> None:
    decision = report["decision"]
    assert decision["promote"] is False
    assert decision["publicPromotion"] is False
    assert decision["keepExperimental"] is True
    assert decision["basedOnThisSmokeOnly"] is True
    assert decision["notAStatisticalSaving"] is True
    assert decision["doNotStartH1"] is True
    assert decision["targetedFix"] is False
    assert "H1" in decision["next"]
    joined = " ".join(decision["reasons"])
    assert "B_template" in joined
    assert "B0" in joined


def test_latency_first_repeat_recorded_without_cold_hot_lies(report: dict) -> None:
    cell = _cell(report, ARM_P_PACK, TASK_P1)
    assert "first" in cell["latencyMs"]
    assert "repeat" in cell["latencyMs"]
    assert "cold" not in cell["latencyMs"]
    assert "hot" not in cell["latencyMs"]
    assert cell["trials"][0]["label"] == "first"
    assert cell["trials"][1]["label"] == "repeat"
    assert cell["trialsDisagree"] is False
    assert report["complete"] is True
    assert report["executionPlan"]["arms"] == list(PRIMARY_ARMS)
    assert report["prep"]["B_template"]["identityHoldsInSymPy"] is True
    assert report["prep"]["B_codegen"]["exactNotFloat"] is True
    assert report["prep"]["B_codegen"]["selfCheckP0"] == "55"


def test_harness_source_does_not_hardcode_latency_figures() -> None:
    for path in HARNESS_FILES:
        text = path.read_text(encoding="utf-8")
        assert '"cold"' not in text
        assert '"hot"' not in text
        lowered = text.lower()
        assert "savings %" not in lowered


def test_decision_does_not_invent_a_latency_observation() -> None:
    cells = [
        {
            "arm": arm,
            "task": task,
            "scoring": {
                "matchedPreRegisteredExpectation": True,
                "wrongAcceptance": False,
                "applicabilityMisjudgment": False,
                "countedAsSolved": task not in {TASK_NEGATIVE, TASK_REVERSED},
                "coversOriginalTaskClaim": False,
                "formalKernelChecked": False,
                "baselineEmbedded": False,
                "reconstructedOnPackArm": False,
                "floatingApproximation": False,
                "usedSavedContent": arm in {ARM_B_TEMPLATE, ARM_B_CODEGEN, ARM_P_PACK},
                "gosperCalledJsonFlag": False if arm == ARM_P_PACK else None,
                "reconstructionDisabled": True if arm == ARM_P_PACK else None,
                "constructionTrace": {
                    "gosper_sum": 0 if arm != ARM_B1 else 1,
                    "construct_antidifference": 0 if arm != ARM_B1 else 1,
                },
                "lifecycleEvidence": LIFECYCLE_VERIFIED if (arm == ARM_P_PACK and task == TASK_P0) else None,
            },
            "summary": {"valueExact": "55" if task in IN_FAMILY_TASKS else None},
        }
        for arm in PRIMARY_ARMS
        for task in (TASK_P0, TASK_P1, TASK_P2, TASK_P3, TASK_P4, TASK_NEGATIVE, TASK_REVERSED)
    ]
    assert observed_slower_checked_path(cells) is None
    decision = decide(
        cells,
        stripped={"refused": True},
        wrong_g={"failClosed": True, "emittedValue": False},
        fair_baselines={
            "b0ValueExact": "44100",
            "b1ValueExact": "44100",
            "pPackRefused": True,
            "templateRefused": True,
            "codegenRefused": True,
        },
        codegen_skip={
            "sympy.utilities.codegen.C": {
                "used": False,
                "probe": {"available": True, "emitsFloatingType": True},
            }
        },
    )
    assert decision.get("observedSlowerCheckedPath") is not True
    assert decision.get("observedSlowerCheckedPath") is None
    assert decision["promote"] is False
    assert decision["judgments"]["notCollapsedIntoOneSuccess"] is True


def test_cli_writes_report_and_refuses_overwrite(tmp_path: Path, report: dict) -> None:
    path = tmp_path / "reuse-benefit-report.json"
    write_report(path, report)
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored["kind"] == REPORT_KIND
    assert stored["decision"]["promote"] is False
    with pytest.raises(Exception, match="refusing to overwrite"):
        write_report(path, report)


def test_cli_end_to_end(tmp_path: Path) -> None:
    output = tmp_path / "reuse-benefit-report.json"
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
    assert stored["judgments"]["utility"]["verdict"] == "no_net_benefit_vs_strong_baselines"
    stdout = json.loads(completed.stdout)
    assert stdout["decision"]["verdict"] == "evidence_insufficient"
    p1 = next(
        cell
        for cell in stored["cells"]
        if cell["arm"] == ARM_P_PACK and cell["task"] == TASK_P1
    )
    assert p1["summary"]["valueExact"] == "355"
    assert p1["scoring"]["constructionTrace"]["gosper_sum"] == 0
