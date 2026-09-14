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
from research.method_packs.apply import apply_method_pack
from research.method_packs.format import DEFAULT_PARAM_PACK_PATH, PARAM_PACK_ID
from research.method_packs.loader import load_pack
from research.reuse_benefit_eval.arms import (
    run_b0,
    run_b_codegen,
    run_b_template,
    run_p_pack,
    trace_construction_calls,
)
from research.reuse_benefit_eval.protocol import (
    ARM_B0,
    ARM_B1,
    ARM_B_CODEGEN,
    ARM_B_TEMPLATE,
    ARM_P_PACK,
    B0_HARMONIC_EXACT,
    CONSTRUCTION_TRACE_KEYS,
    HELD_OUT_TASKS,
    IN_FAMILY_TASKS,
    LIFECYCLE_CROSS_TASK,
    LIFECYCLE_VERIFIED,
    MANDATORY_CLAIM_LATENCY_FASTER_THAN_TEMPLATE_ZH,
    MANDATORY_CLAIM_LATENCY_NOT_FASTER_ZH,
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
    reconcile_mandatory_claim_answer_zh,
    task_by_id,
    validate_protocol,
)
from research.reuse_benefit_eval.score import (
    decide,
    observed_slower_checked_path,
    result_summary,
    score_cell,
    three_judgments,
)
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
    assert MANDATORY_CLAIM_LATENCY_NOT_FASTER_ZH in protocol["mandatoryClaimAnswerZh"]
    assert by_id[TASK_NEGATIVE]["expectedByArm"][ARM_B0]["expectedExactIfComputed"] == B0_HARMONIC_EXACT


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

    mutated_zh = deepcopy(original)
    mutated_zh["mandatoryClaimAnswerZh"] = original["mandatoryClaimAnswerZh"].replace(
        MANDATORY_CLAIM_LATENCY_NOT_FASTER_ZH,
        "本机耗时更低",
    )
    with pytest.raises(ValueError, match="pre-registered mandatory Chinese answer"):
        validate_protocol(mutated_zh)
    with pytest.raises(ValueError, match="pre-registered mandatory Chinese answer"):
        run_smoke(protocol=mutated_zh)


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
    assert cell["scoring"]["constructionTrace"]["summation"] == 0
    assert cell["scoring"]["constructionTrace"]["Sum.doit"] == 0
    assert cell["scoring"]["constructionProbe"] == "wrap"
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
        assert cell["scoring"]["constructionTrace"]["summation"] == 0
        assert cell["scoring"]["constructionTrace"]["Sum.doit"] == 0
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
        assert cell["scoring"]["constructionTrace"]["summation"] == 0
        assert cell["scoring"]["constructionTrace"]["Sum.doit"] == 0
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
    assert b0["summary"]["valueExact"] == B0_HARMONIC_EXACT
    assert b0["scoring"]["matchedPreRegisteredExpectation"] is True
    assert b0["scoring"]["countedAsSolved"] is False
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
    assert trust["classifiedFromStructuredProbes"] is True
    assert trust["probes"]["strippedRefused"] is True
    assert trust["probes"]["wrongGFailClosed"] is True
    assert trust["probes"]["inFamilyPPackMatched"] is True
    assert "stripped parametricAntidifference refuses" in trust["evidence"]
    assert "in-family match failed" not in trust["evidence"]
    assert behavior["verdict"] == "pack_uses_saved_content"
    assert behavior["notUtility"] is True
    assert behavior["packReuseIsNotUniqueVsTemplate"] is True
    assert behavior["constructionProbe"] == "wrap"
    assert utility["verdict"] == "no_net_benefit_vs_strong_baselines"
    assert utility["mayBeNegative"] is True
    assert utility["fasterThanColdGosperIsNotUniqueness"] is True
    assert utility["bTemplateAlreadyMatchesP"] is True
    assert report["decision"]["verdict"] == "evidence_insufficient"
    assert report["decision"]["promote"] is False
    assert "success" not in report["decision"] or report["decision"].get("success") is not True
    faster_than_template = report["decision"]["observedPackRepeatFasterThanTemplate"]
    if faster_than_template is True:
        assert MANDATORY_CLAIM_LATENCY_NOT_FASTER_ZH not in report["mandatoryClaimAnswerZh"]
        assert MANDATORY_CLAIM_LATENCY_FASTER_THAN_TEMPLATE_ZH in report["mandatoryClaimAnswerZh"]
    elif faster_than_template is False:
        assert MANDATORY_CLAIM_LATENCY_NOT_FASTER_ZH in report["mandatoryClaimAnswerZh"]
    assert report["honesty"]["mandatoryClaimLatencyClauseGeneratedFromFlags"] is True
    assert report["honesty"]["mandatoryClaimAnswerZhPinned"] is True
    assert report["mandatoryClaimAnswerZhPinned"] == load_protocol()["mandatoryClaimAnswerZh"]
    assert report["honesty"]["constructionWrapIsTheBindingProbe"] is True
    assert report["honesty"]["usedSavedContentComesFromApply"] is True
    assert report["mandatoryClaimLatencyClauseZh"] == (
        MANDATORY_CLAIM_LATENCY_FASTER_THAN_TEMPLATE_ZH
        if faster_than_template is True
        else (
            MANDATORY_CLAIM_LATENCY_NOT_FASTER_ZH
            if faster_than_template is False
            else report["mandatoryClaimLatencyClauseZh"]
        )
    )


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
                    "summation": 0,
                    "Sum.doit": 0,
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
    assert p1["scoring"]["constructionTrace"]["summation"] == 0
    assert p1["scoring"]["constructionTrace"]["Sum.doit"] == 0
    assert p1["scoring"]["constructionProbe"] == "wrap"
    assert stored["decision"]["promote"] is False
    assert stored["decision"]["verdict"] == "evidence_insufficient"


_GREEN_CODEGEN_SKIP = {
    "sympy.utilities.codegen.C": {
        "used": False,
        "probe": {"available": True, "emitsFloatingType": True},
    }
}
_GREEN_FAIR_BASELINES = {
    "b0ValueExact": "44100",
    "b1ValueExact": "44100",
    "pPackRefused": True,
    "templateRefused": True,
    "codegenRefused": True,
}


def _stub_cell(arm: str, task: str, **scoring_extra) -> dict:
    scoring = {
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
            "summation": 0,
            "Sum.doit": 0,
        },
        "lifecycleEvidence": (
            LIFECYCLE_VERIFIED
            if arm == ARM_P_PACK and task == TASK_P0
            else (LIFECYCLE_CROSS_TASK if arm == ARM_P_PACK and task in HELD_OUT_TASKS else None)
        ),
    }
    scoring.update(scoring_extra)
    error_code = None
    if task == TASK_NEGATIVE and arm != ARM_B0:
        error_code = "E_UNSUPPORTED"
    elif task == TASK_REVERSED and arm not in {ARM_B0, ARM_B_TEMPLATE, ARM_B_CODEGEN}:
        error_code = "E_DOMAIN"
    return {
        "arm": arm,
        "task": task,
        "scoring": scoring,
        "summary": {
            "valueExact": "55" if task in IN_FAMILY_TASKS else None,
            "errorCode": error_code,
        },
    }


def test_strip_failure_is_trust_fails_from_structured_probe() -> None:
    decision = decide(
        [],
        stripped={"refused": False},
        wrong_g={"failClosed": True, "emittedValue": False},
        fair_baselines=_GREEN_FAIR_BASELINES,
        codegen_skip=_GREEN_CODEGEN_SKIP,
    )
    trust = decision["judgments"]["trustworthiness"]
    assert decision["verdict"] == "targeted_fix"
    assert decision["promote"] is False
    assert trust["verdict"] == "fails"
    assert trust["classifiedFromStructuredProbes"] is True
    assert trust["probes"]["strippedRefused"] is False
    assert "stripped parametricAntidifference refuses" not in trust["evidence"]
    assert any("did not refuse" in line for line in trust["evidence"])


def test_wrong_g_failure_is_trust_fails_from_structured_probe() -> None:
    decision = decide(
        [_stub_cell(ARM_P_PACK, task) for task in IN_FAMILY_TASKS],
        stripped={"refused": True},
        wrong_g={"failClosed": False, "emittedValue": True},
        fair_baselines=_GREEN_FAIR_BASELINES,
        codegen_skip=_GREEN_CODEGEN_SKIP,
    )
    trust = decision["judgments"]["trustworthiness"]
    assert trust["verdict"] == "fails"
    assert trust["probes"]["wrongGFailClosed"] is False
    assert "wrong saved G fail-closes without emitting a sum" not in trust["evidence"]
    assert any("emitted" in line for line in trust["evidence"])


def test_b1_construction_miss_does_not_rewrite_in_family_trust_evidence() -> None:
    cells = [_stub_cell(ARM_P_PACK, task) for task in IN_FAMILY_TASKS]
    cells.append(
        _stub_cell(
            ARM_B1,
            TASK_P0,
            constructionTrace={"gosper_sum": 0, "construct_antidifference": 0},
        )
    )
    decision = decide(
        cells,
        stripped={"refused": True},
        wrong_g={"failClosed": True, "emittedValue": False},
        fair_baselines=_GREEN_FAIR_BASELINES,
        codegen_skip=_GREEN_CODEGEN_SKIP,
    )
    assert any("B1" in item and "did not construct" in item for item in decision["problems"])
    trust = decision["judgments"]["trustworthiness"]
    assert trust["probes"]["inFamilyPPackMatched"] is True
    assert "in-family P-pack values match the pre-registered rationals" in trust["evidence"]
    assert "in-family match failed" not in trust["evidence"]
    assert trust["verdict"] == "holds_in_declared_domain"


def test_b0_harmonic_match_requires_protocol_exact_not_any_ok_value() -> None:
    task = task_by_id(TASK_NEGATIVE)
    garbage = score_cell(
        arm_id=ARM_B0,
        task=task,
        summary={"status": "ok", "valueExact": "999"},
        construction={"gosper_sum": 0, "construct_antidifference": 0},
    )
    assert garbage["matchedPreRegisteredExpectation"] is False
    assert garbage["countedAsSolved"] is False
    assert garbage["wrongAcceptance"] is False

    harmonic = score_cell(
        arm_id=ARM_B0,
        task=task,
        summary={"status": "ok", "valueExact": B0_HARMONIC_EXACT},
        construction={"gosper_sum": 0, "construct_antidifference": 0},
    )
    assert harmonic["matchedPreRegisteredExpectation"] is True
    assert harmonic["countedAsSolved"] is False

    garbage_cell = {
        "arm": ARM_B0,
        "task": TASK_NEGATIVE,
        "scoring": garbage,
        "summary": {"status": "ok", "valueExact": "999"},
    }
    decision = decide(
        [garbage_cell],
        stripped={"refused": True},
        wrong_g={"failClosed": True, "emittedValue": False},
        fair_baselines=_GREEN_FAIR_BASELINES,
        codegen_skip=_GREEN_CODEGEN_SKIP,
    )
    assert any("B0×negative-harmonic" in item and "did not match" in item for item in decision["problems"])
    assert decision["verdict"] == "targeted_fix"
    assert decision["promote"] is False


def test_contradicting_frozen_chinese_latency_clause_is_overwritten_by_flags() -> None:
    frozen = load_protocol()["mandatoryClaimAnswerZh"]
    assert MANDATORY_CLAIM_LATENCY_NOT_FASTER_ZH in frozen
    overwritten = reconcile_mandatory_claim_answer_zh(
        frozen,
        observed_pack_faster_than_template=True,
    )
    assert overwritten["overwrittenBecauseLatencyFlagsDisagreed"] is True
    assert overwritten["consistentWithLatencyFlags"] is False
    assert MANDATORY_CLAIM_LATENCY_NOT_FASTER_ZH not in overwritten["answerZh"]
    assert MANDATORY_CLAIM_LATENCY_FASTER_THAN_TEMPLATE_ZH in overwritten["answerZh"]
    assert overwritten["latencyClauseZh"] == MANDATORY_CLAIM_LATENCY_FASTER_THAN_TEMPLATE_ZH

    consistent = reconcile_mandatory_claim_answer_zh(
        frozen,
        observed_pack_faster_than_template=False,
    )
    assert consistent["overwrittenBecauseLatencyFlagsDisagreed"] is False
    assert consistent["consistentWithLatencyFlags"] is True
    assert MANDATORY_CLAIM_LATENCY_NOT_FASTER_ZH in consistent["answerZh"]


def test_p_pack_used_saved_content_comes_from_apply_and_wrap_is_the_probe() -> None:
    source = (ROOT / "research" / "reuse_benefit_eval" / "arms.py").read_text(encoding="utf-8")
    p_block = source.split("def run_p_pack")[1].split("def is_arm_exception")[0]
    assert 'wrapped["usedSavedContent"] = True' not in p_block
    pack = load_pack(DEFAULT_PARAM_PACK_PATH)
    result = apply_method_pack(
        {
            "summand": "(k+3)^2",
            "variable": "k",
            "lower": 2,
            "upper": 7,
            "parameterC": "3",
            "taskId": "P1-shifted-square-c3-2-to-7",
        },
        pack=pack,
        compare_baseline=False,
    )
    assert result["usedSavedContent"] is True
    assert result["constructor"] == "instantiated-saved-parametric-antidifference"
    assert result["gosperCalled"] is False


def _zero_construction() -> dict[str, int]:
    return {key: 0 for key in CONSTRUCTION_TRACE_KEYS}


def test_construction_probe_counts_synthetic_summation_and_sum_doit() -> None:
    import sympy as sp

    k = sp.symbols("k")
    with trace_construction_calls() as counts:
        sp.summation(k, (k, 0, 3))
    assert counts["summation"] >= 1
    assert set(counts) == set(CONSTRUCTION_TRACE_KEYS)

    with trace_construction_calls() as counts:
        sp.Sum(k, (k, 0, 3)).doit()
    assert counts["Sum.doit"] >= 1


@pytest.mark.parametrize("key", ["summation", "Sum.doit"])
def test_p_pack_synthetic_cas_reconstruction_is_detected(key: str) -> None:
    construction = _zero_construction()
    construction[key] = 1
    scoring = score_cell(
        arm_id=ARM_P_PACK,
        task=task_by_id(TASK_P1),
        summary={
            "status": "ok",
            "valueExact": "355",
            "usedSavedContent": True,
            "gosperCalled": False,
            "reconstructionDisabled": True,
            "formalKernelChecked": False,
            "baselineEmbedded": False,
            "floatingApproximation": False,
            "independentChecker": True,
            "stepsExecuted": ["retrieve", "instantiate"],
            "adoption": {
                "lifecycleEvidence": LIFECYCLE_CROSS_TASK,
                "callAloneIsNotAdoption": True,
            },
        },
        construction=construction,
    )
    assert scoring["reconstructedOnPackArm"] is True
    assert scoring["constructionTrace"][key] == 1
    decision = decide(
        [
            {
                "arm": ARM_P_PACK,
                "task": TASK_P1,
                "scoring": scoring,
                "summary": {"valueExact": "355"},
            }
        ],
        stripped={"refused": True},
        wrong_g={"failClosed": True, "emittedValue": False},
        fair_baselines=_GREEN_FAIR_BASELINES,
        codegen_skip=_GREEN_CODEGEN_SKIP,
    )
    assert any("summation" in item or "Sum.doit" in item for item in decision["problems"])
    assert decision["verdict"] == "targeted_fix"
    assert decision["promote"] is False
    assert decision["judgments"]["behavior"]["verdict"] == "re_solves"


def test_b0_summation_under_wrap_is_not_pack_reconstruction() -> None:
    with trace_construction_calls() as counts:
        result = run_b0(
            {
                "summand": "(k+1)^2",
                "variable": "k",
                "lower": 0,
                "upper": 4,
            }
        )
    assert result["status"] == "ok"
    assert result["value"]["exact"] == "55"
    assert counts["summation"] >= 1
    scoring = score_cell(
        arm_id=ARM_B0,
        task=task_by_id(TASK_P0),
        summary={
            "status": "ok",
            "valueExact": "55",
            "usedSavedContent": False,
            "gosperCalled": False,
            "formalKernelChecked": False,
            "baselineEmbedded": False,
            "floatingApproximation": False,
            "stepsExecuted": ["cas_summation"],
        },
        construction=counts,
    )
    assert scoring["reconstructedOnPackArm"] is False
    assert scoring["countedAsSolved"] is True
    assert scoring["constructionTrace"]["summation"] >= 1


def test_b0_live_summation_is_traced_and_not_crippled(report: dict) -> None:
    cell = _cell(report, ARM_B0, TASK_P1)
    assert cell["summary"]["valueExact"] == "355"
    assert cell["summary"]["status"] == "ok"
    assert cell["scoring"]["constructionTrace"]["summation"] >= 1
    assert cell["scoring"]["reconstructedOnPackArm"] is False
    assert cell["scoring"]["countedAsSolved"] is True


def test_p_pack_completes_when_summation_and_sum_doit_explode(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("P-pack must not reconstruct via summation or Sum.doit")

    monkeypatch.setattr("sympy.summation", boom)
    monkeypatch.setattr("sympy.concrete.summations.summation", boom)
    monkeypatch.setattr("sympy.Sum.doit", boom)
    result = run_p_pack(
        {
            "summand": "(k+3)^2",
            "variable": "k",
            "lower": 2,
            "upper": 7,
            "parameterC": "3",
            "taskId": "P1-shifted-square-c3-2-to-7",
        }
    )
    assert result["status"] == "ok"
    assert result["value"]["exact"] == "355"
    assert result["usedSavedContent"] is True


def test_used_saved_content_on_falsified_identity_does_not_establish_a_value() -> None:
    pack = json.loads(Path(DEFAULT_PARAM_PACK_PATH).read_text(encoding="utf-8"))
    semantics = pack.get("mathSemantics")
    assert isinstance(semantics, dict)
    semantics["parametricAntidifference"]["source"] = "k"
    result = apply_method_pack(
        {
            "summand": "(k+3)^2",
            "variable": "k",
            "lower": 2,
            "upper": 7,
            "parameterC": "3",
            "taskId": "P1-shifted-square-c3-2-to-7",
        },
        pack=pack,
        compare_baseline=False,
    )
    assert result["status"] == "falsified"
    assert result["usedSavedContent"] is True
    assert "value" not in result
    summary = result_summary(result, None)
    scoring = score_cell(
        arm_id=ARM_P_PACK,
        task=task_by_id(TASK_P1),
        summary=summary,
        construction=_zero_construction(),
    )
    assert scoring["usedSavedContent"] is True
    assert scoring["countedAsSolved"] is False
    assert scoring["matchedPreRegisteredExpectation"] is False
    assert scoring["applicabilityMisjudgment"] is True
    decision = decide(
        [
            {
                "arm": ARM_P_PACK,
                "task": TASK_P1,
                "scoring": scoring,
                "summary": summary,
            }
        ],
        stripped={"refused": True},
        wrong_g={"failClosed": True, "emittedValue": False},
        fair_baselines=_GREEN_FAIR_BASELINES,
        codegen_skip=_GREEN_CODEGEN_SKIP,
    )
    assert decision["verdict"] == "targeted_fix"
    assert decision["promote"] is False


def test_three_judgments_does_not_take_a_dead_problems_parameter() -> None:
    assert "problems" not in inspect.signature(three_judgments).parameters
    garbage = score_cell(
        arm_id=ARM_B0,
        task=task_by_id(TASK_NEGATIVE),
        summary={"status": "ok", "valueExact": "999"},
        construction=_zero_construction(),
    )
    decision = decide(
        [
            {
                "arm": ARM_B0,
                "task": TASK_NEGATIVE,
                "scoring": garbage,
                "summary": {"status": "ok", "valueExact": "999"},
            }
        ],
        stripped={"refused": True},
        wrong_g={"failClosed": True, "emittedValue": False},
        fair_baselines=_GREEN_FAIR_BASELINES,
        codegen_skip=_GREEN_CODEGEN_SKIP,
    )
    assert decision["problems"]
    assert decision["verdict"] == "targeted_fix"
    assert decision["promote"] is False
