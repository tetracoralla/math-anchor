"""Honesty tests for the trust/fail-closed vs fair template smoke.

Green tests here record the pre-registered protocol and the fail-closed vs
silent-wrong distinctions. They are not completion of a promotion claim and
not a latency bake-off. Do not hardcode millisecond figures.
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

from research.method_packs.format import PARAM_PACK_ID
from research.method_packs.shifted_square import CANONICAL_G_SOURCE, parse_bivariate
from research.reuse_benefit_eval.template import CACHED_G, _C, _K
from research.trust_failclosed_eval.arms import run_b_template, run_p_pack
from research.trust_failclosed_eval.protocol import (
    ARM_B_TEMPLATE,
    ARM_P_PACK,
    CONTROL_EXACT,
    KARR_REVERSED_EXACT,
    MANDATORY_CLAIM_DIFFERENTIATION_ZH,
    MANDATORY_CLAIM_LATENCY_NOT_PRIMARY_ZH,
    MANDATORY_CLAIM_NO_SAVED_G_DIFF_ZH,
    OVER_LIMIT_EXACT,
    PRIMARY_ARMS,
    PROTOCOL_KIND,
    REPORT_KIND,
    SWAPPED_G_TEMPLATE_EXACT,
    TASK_CONTROL,
    TASK_CUBES,
    TASK_HARMONIC,
    TASK_OVER_LIMIT,
    TASK_PARAMETER,
    TASK_REVERSED,
    TASK_SWAPPED_G,
    TASK_WRONG_G,
    TRUST_FAIL_CLOSED,
    TRUST_HOLDS,
    TRUST_SCALE,
    TRUST_SILENT_ACCEPT,
    TRUST_SILENT_WRONG,
    WRONG_G_TEMPLATE_EXACT,
    load_protocol,
    protocol_digest,
    reconcile_mandatory_claim_answer_zh,
    saved_g_source,
    task_by_id,
    validate_protocol,
)
from research.trust_failclosed_eval.score import classify_trust, decide, score_cell
from research.trust_failclosed_eval.smoke import run_smoke, write_report


RUNNER = ROOT / "research" / "trust_failclosed_eval" / "run.py"
HARNESS_FILES = (
    ROOT / "research" / "trust_failclosed_eval" / "protocol.py",
    ROOT / "research" / "trust_failclosed_eval" / "arms.py",
    ROOT / "research" / "trust_failclosed_eval" / "probes.py",
    ROOT / "research" / "trust_failclosed_eval" / "score.py",
    ROOT / "research" / "trust_failclosed_eval" / "smoke.py",
    ROOT / "research" / "trust_failclosed_eval" / "run.py",
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
    assert protocol["notALatencyBakeOff"] is True
    assert protocol["judgmentsAreSeparate"] is True
    assert protocol["model"]["callsAllowed"] is False
    assert protocol["budget"]["dollarCosts"] is None
    ids = [task["id"] for task in protocol["tasks"]]
    assert ids == [
        TASK_CONTROL,
        TASK_WRONG_G,
        TASK_SWAPPED_G,
        TASK_CUBES,
        TASK_HARMONIC,
        TASK_REVERSED,
        TASK_PARAMETER,
        TASK_OVER_LIMIT,
    ]
    arms = [arm["id"] for arm in protocol["arms"]]
    assert tuple(arms) == PRIMARY_ARMS
    scale = protocol["trustworthinessScale"]
    assert tuple(scale) == TRUST_SCALE
    assert set(scale) == set(TRUST_SCALE)
    template = next(arm for arm in protocol["arms"] if arm["id"] == ARM_B_TEMPLATE)
    assert template["packIdentityChecks"] is False
    assert template["packDomainChecks"] is False
    assert template["familyMatching"] is True
    pack = next(arm for arm in protocol["arms"] if arm["id"] == ARM_P_PACK)
    assert pack["reconstructionDisabled"] is True
    assert pack["packId"] == PARAM_PACK_ID
    assert protocol["latency"]["primaryClaim"] is False
    assert protocol["latency"]["trials"] == 1
    assert MANDATORY_CLAIM_DIFFERENTIATION_ZH in protocol["mandatoryClaimAnswerZh"]
    assert MANDATORY_CLAIM_LATENCY_NOT_PRIMARY_ZH in protocol["mandatoryClaimAnswerZh"]
    assert protocol["tasks"][1]["expectedByArm"][ARM_B_TEMPLATE]["expectedExactIfComputed"] == WRONG_G_TEMPLATE_EXACT


def test_unsupported_protocol_overrides_are_rejected() -> None:
    original = load_protocol()
    only_pack = deepcopy(original)
    only_pack["arms"] = [arm for arm in only_pack["arms"] if arm["id"] == ARM_P_PACK]
    with pytest.raises(ValueError, match="pre-registered"):
        validate_protocol(only_pack)
    with pytest.raises(ValueError, match="pre-registered"):
        run_smoke(protocol=only_pack)

    two_trials = deepcopy(original)
    two_trials["latency"] = {**two_trials["latency"], "trials": 2}
    with pytest.raises(ValueError, match="pre-registered"):
        validate_protocol(two_trials)

    mutated_task = deepcopy(original)
    mutated_task["tasks"][0]["expectedExact"] = "0"
    with pytest.raises(ValueError, match="pre-registered"):
        validate_protocol(mutated_task)

    mutated_zh = deepcopy(original)
    mutated_zh["mandatoryClaimAnswerZh"] = original["mandatoryClaimAnswerZh"].replace(
        MANDATORY_CLAIM_DIFFERENTIATION_ZH,
        "包在所有探针上都更快",
    )
    with pytest.raises(ValueError, match="pre-registered mandatory Chinese answer"):
        validate_protocol(mutated_zh)

    mutated_honesty = deepcopy(original)
    mutated_honesty["honesty"] = {**mutated_honesty["honesty"], "formalKernelChecked": True}
    with pytest.raises(ValueError, match="pre-registered honesty"):
        validate_protocol(mutated_honesty)

    mutated_scoring = deepcopy(original)
    mutated_scoring["scoring"] = {**mutated_scoring["scoring"], "coversOriginalTaskClaim": "true"}
    with pytest.raises(ValueError, match="pre-registered scoring"):
        validate_protocol(mutated_scoring)

    mutated_rule = deepcopy(original)
    mutated_rule["decisionRule"] = {**mutated_rule["decisionRule"], "promote": "allowed"}
    with pytest.raises(ValueError, match="pre-registered decisionRule"):
        validate_protocol(mutated_rule)


def test_control_both_hold_in_family(report: dict) -> None:
    for arm in PRIMARY_ARMS:
        cell = _cell(report, arm, TASK_CONTROL)
        assert cell["summary"]["valueExact"] == CONTROL_EXACT
        assert cell["summary"]["status"] == "ok"
        assert cell["scoring"]["trustworthiness"] == TRUST_HOLDS
        assert cell["scoring"]["countedAsSolved"] is True
        assert cell["scoring"]["coversOriginalTaskClaim"] is False
        assert cell["summary"]["floatingApproximation"] is False


def test_wrong_saved_g_pack_fail_closed_template_silent_wrong(report: dict) -> None:
    pack = _cell(report, ARM_P_PACK, TASK_WRONG_G)
    template = _cell(report, ARM_B_TEMPLATE, TASK_WRONG_G)
    assert pack["scoring"]["trustworthiness"] == TRUST_FAIL_CLOSED
    assert pack["scoring"]["emittedValue"] is False
    assert pack["summary"]["valueExact"] is None
    assert pack["summary"]["status"] in {"falsified", "error", "inapplicable"}
    assert template["scoring"]["trustworthiness"] == TRUST_SILENT_WRONG
    assert template["scoring"]["wrongAcceptance"] is True
    assert template["scoring"]["silentAcceptance"] is not True
    assert template["summary"]["status"] == "ok"
    assert template["summary"]["valueExact"] == WRONG_G_TEMPLATE_EXACT
    assert template["summary"]["valueExact"] != CONTROL_EXACT


def test_swapped_saved_g_pack_fail_closed_template_silent_wrong(report: dict) -> None:
    pack = _cell(report, ARM_P_PACK, TASK_SWAPPED_G)
    template = _cell(report, ARM_B_TEMPLATE, TASK_SWAPPED_G)
    assert pack["scoring"]["trustworthiness"] == TRUST_FAIL_CLOSED
    assert pack["scoring"]["emittedValue"] is False
    assert template["scoring"]["trustworthiness"] == TRUST_SILENT_WRONG
    assert template["scoring"]["wrongAcceptance"] is True
    assert template["summary"]["valueExact"] == SWAPPED_G_TEMPLATE_EXACT


def test_out_of_family_both_fail_closed_not_pack_unique(report: dict) -> None:
    for task_id in (TASK_CUBES, TASK_HARMONIC):
        for arm in PRIMARY_ARMS:
            cell = _cell(report, arm, task_id)
            assert cell["scoring"]["trustworthiness"] == TRUST_FAIL_CLOSED
            assert cell["scoring"]["countedAsSolved"] is False
            assert cell["summary"]["valueExact"] is None
            assert cell["summary"]["errorCode"] == "E_UNSUPPORTED"


def test_reversed_bounds_pack_fail_closed_template_karr_silent_accept(report: dict) -> None:
    pack = _cell(report, ARM_P_PACK, TASK_REVERSED)
    template = _cell(report, ARM_B_TEMPLATE, TASK_REVERSED)
    assert pack["scoring"]["trustworthiness"] == TRUST_FAIL_CLOSED
    assert pack["summary"]["errorCode"] == "E_DOMAIN"
    assert pack["summary"]["valueExact"] is None
    assert template["scoring"]["trustworthiness"] == TRUST_SILENT_ACCEPT
    assert template["scoring"]["wrongAcceptance"] is False
    assert template["scoring"]["silentAcceptance"] is True
    assert template["summary"]["valueExact"] == KARR_REVERSED_EXACT
    assert template["summary"]["karrReversedBoundsAccepted"] is True


def test_parameter_mismatch_both_fail_closed(report: dict) -> None:
    for arm in PRIMARY_ARMS:
        cell = _cell(report, arm, TASK_PARAMETER)
        assert cell["scoring"]["trustworthiness"] == TRUST_FAIL_CLOSED
        assert cell["summary"]["errorCode"] == "E_DOMAIN"
        assert cell["scoring"]["countedAsSolved"] is False


def test_over_limit_pack_fail_closed_template_silent_accept(report: dict) -> None:
    pack = _cell(report, ARM_P_PACK, TASK_OVER_LIMIT)
    template = _cell(report, ARM_B_TEMPLATE, TASK_OVER_LIMIT)
    assert pack["scoring"]["trustworthiness"] == TRUST_FAIL_CLOSED
    assert pack["summary"]["errorCode"] == "E_LIMIT"
    assert pack["summary"]["valueExact"] is None
    assert template["scoring"]["trustworthiness"] == TRUST_SILENT_ACCEPT
    assert template["scoring"]["wrongAcceptance"] is False
    assert template["scoring"]["silentAcceptance"] is True
    assert template["summary"]["valueExact"] == OVER_LIMIT_EXACT
    assert template["scoring"]["trustReason"] == "silent_accept_out_of_declared_pack_domain"


def test_stripped_payload_and_binding_mismatch(report: dict) -> None:
    stripped = report["structuralProbes"]["strippedPayload"]
    assert stripped["refused"] is True
    binding = report["structuralProbes"]["bindingMismatch"]
    assert binding["packGoodResultBindingHolds"] is True
    assert binding["packTamperedIdentityFailClosed"] is True
    assert binding["templateHasObligationBindingHook"] is not True
    assert "verify_typed_binding" in binding["hook"]


def test_p_pack_control_does_not_reconstruct(report: dict) -> None:
    cell = _cell(report, ARM_P_PACK, TASK_CONTROL)
    assert cell["summary"]["constructor"] == "instantiated-saved-parametric-antidifference"
    assert cell["summary"]["gosperCalled"] is False
    assert cell["summary"]["reconstructionDisabled"] is True
    assert cell["scoring"]["constructionTrace"]["gosper_sum"] == 0
    assert cell["scoring"]["constructionTrace"]["construct_antidifference"] == 0
    assert cell["scoring"]["constructionTrace"]["summation"] == 0
    assert cell["scoring"]["constructionTrace"]["Sum.doit"] == 0
    assert cell["scoring"]["usedSavedContent"] is True
    assert cell["scoring"]["reconstructedOnPackArm"] is False
    steps = cell["summary"]["stepsExecuted"]
    assert "verify_general_difference_identity" in steps
    assert "verify_difference_identity" in steps


def test_template_does_not_apply_pack_or_check_obligations() -> None:
    names = run_b_template.__code__.co_names
    assert "apply_method_pack" not in names
    assert "check_obligation_set" not in names
    source = (ROOT / "research" / "trust_failclosed_eval" / "arms.py").read_text(encoding="utf-8")
    template_block = source.split("def run_p_pack")[0]
    assert "apply_method_pack" not in template_block
    assert "evaluate_template" in template_block
    tree = ast.parse(inspect.getsource(run_b_template))
    collected: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            collected.add(node.id)
    assert "eval" not in collected
    assert "exec" not in collected


def test_three_judgments_are_separate_and_not_one_success(report: dict) -> None:
    judgments = report["judgments"]
    assert judgments["notCollapsedIntoOneSuccess"] is True
    assert set(judgments) >= {"trustworthiness", "behavior", "utility", "notCollapsedIntoOneSuccess"}
    trust = judgments["trustworthiness"]
    behavior = judgments["behavior"]
    utility = judgments["utility"]
    assert trust["appliedPerCell"] is True
    assert trust["scale"] == list(TRUST_SCALE)
    assert trust["control"]["P-pack"] == TRUST_HOLDS
    assert trust["control"]["B_template"] == TRUST_HOLDS
    assert trust["observedContrast"][TASK_WRONG_G]["differentiates"] is True
    assert trust["observedContrast"][TASK_CUBES]["differentiates"] is not True
    assert behavior["verdict"] == "pack_uses_saved_content"
    assert utility["verdict"] == "not_the_primary_claim"
    assert utility["latencyIsNotThePrimaryClaim"] is True
    assert report["decision"]["verdict"] == "evidence_insufficient"
    assert report["decision"]["experimentVerdict"] == "differentiation_observed"
    assert report["decision"]["promote"] is False
    assert report["decision"]["notALatencyBakeOff"] is True
    assert "success" not in report["decision"] or report["decision"].get("success") is not True
    assert MANDATORY_CLAIM_LATENCY_NOT_PRIMARY_ZH in report["mandatoryClaimAnswerZh"]
    assert report["honesty"]["judgmentsAreNotOneSuccessFlag"] is True


def test_decision_is_not_promote(report: dict) -> None:
    decision = report["decision"]
    assert decision["promote"] is False
    assert decision["publicPromotion"] is False
    assert decision["keepExperimental"] is True
    assert decision["doNotStartH1"] is True
    assert decision["targetedFix"] is False
    assert decision["observedWrongGDifferentiation"] is True
    assert decision["observedDomainDifferentiation"] is True
    assert decision["observedOutOfFamilyBothFailClosed"] is True
    assert "H1" in decision["next"]


def test_report_refuses_benefit_percent_latency_bakeoff_and_dollars(report: dict) -> None:
    assert report["kind"] == REPORT_KIND
    assert report["protocolDigest"] == protocol_digest()
    assert report["refusedClaims"]["overallBenefitPercent"]["emitted"] is False
    assert report["refusedClaims"]["dollarCosts"]["emitted"] is False
    assert report["refusedClaims"]["savingsPercent"]["emitted"] is False
    assert report["refusedClaims"]["latencyBakeOff"]["emitted"] is False
    assert report["refusedClaims"]["collapsedSuccessFlag"]["emitted"] is False
    blob = json.dumps(report)
    assert "$" not in blob
    assert "usd" not in blob.lower()
    assert report["model"]["callsAllowed"] is False


def test_latency_is_informational_not_cold_hot(report: dict) -> None:
    cell = _cell(report, ARM_P_PACK, TASK_CONTROL)
    assert "observed" in cell["latencyMs"]
    assert "cold" not in cell["latencyMs"]
    assert "hot" not in cell["latencyMs"]
    assert report["executionPlan"]["trials"] == 1
    assert report["honesty"]["latencyLabelsAreInformational"] is True


def test_harness_source_does_not_hardcode_latency_figures() -> None:
    for path in HARNESS_FILES:
        text = path.read_text(encoding="utf-8")
        assert '"cold"' not in text
        assert '"hot"' not in text
        lowered = text.lower()
        assert "savings %" not in lowered


def test_classify_trust_keeps_four_labels() -> None:
    control = task_by_id(TASK_CONTROL)
    holds = classify_trust(control, ARM_P_PACK, {"status": "ok", "valueExact": "355"})
    assert holds["observed"] == TRUST_HOLDS
    wrong = classify_trust(task_by_id(TASK_WRONG_G), ARM_B_TEMPLATE, {"status": "ok", "valueExact": "6"})
    assert wrong["observed"] == TRUST_SILENT_WRONG
    closed = classify_trust(
        task_by_id(TASK_WRONG_G),
        ARM_P_PACK,
        {"status": "falsified", "valueExact": None, "errorCode": None},
    )
    assert closed["observed"] == TRUST_FAIL_CLOSED
    over = classify_trust(
        task_by_id(TASK_OVER_LIMIT),
        ARM_B_TEMPLATE,
        {"status": "ok", "valueExact": OVER_LIMIT_EXACT},
    )
    assert over["observed"] == TRUST_SILENT_ACCEPT
    missing = classify_trust(control, ARM_P_PACK, {"status": "ok", "valueExact": None})
    assert missing["observed"] == TRUST_FAIL_CLOSED


def _zero_construction() -> dict[str, int]:
    return {"gosper_sum": 0, "construct_antidifference": 0, "summation": 0, "Sum.doit": 0}


def test_silent_wrong_match_requires_expected_exact_if_computed() -> None:
    ignored_mutation = score_cell(
        arm_id=ARM_B_TEMPLATE,
        task=task_by_id(TASK_WRONG_G),
        summary={"status": "ok", "valueExact": CONTROL_EXACT},
        construction=_zero_construction(),
    )
    assert ignored_mutation["trustworthiness"] == TRUST_SILENT_WRONG
    assert ignored_mutation["matchedPreRegisteredExpectation"] is False
    assert ignored_mutation["wrongAcceptance"] is True

    naive = score_cell(
        arm_id=ARM_B_TEMPLATE,
        task=task_by_id(TASK_WRONG_G),
        summary={"status": "ok", "valueExact": WRONG_G_TEMPLATE_EXACT},
        construction=_zero_construction(),
    )
    assert naive["matchedPreRegisteredExpectation"] is True
    assert naive["wrongAcceptance"] is True

    garbage_over_limit = score_cell(
        arm_id=ARM_B_TEMPLATE,
        task=task_by_id(TASK_OVER_LIMIT),
        summary={"status": "ok", "valueExact": "0"},
        construction=_zero_construction(),
    )
    assert garbage_over_limit["trustworthiness"] == TRUST_SILENT_WRONG
    assert garbage_over_limit["matchedPreRegisteredExpectation"] is False
    assert garbage_over_limit["wrongAcceptance"] is True
    assert garbage_over_limit["silentAcceptance"] is not True

    math_correct_over_limit = score_cell(
        arm_id=ARM_B_TEMPLATE,
        task=task_by_id(TASK_OVER_LIMIT),
        summary={"status": "ok", "valueExact": OVER_LIMIT_EXACT},
        construction=_zero_construction(),
    )
    assert math_correct_over_limit["trustworthiness"] == TRUST_SILENT_ACCEPT
    assert math_correct_over_limit["matchedPreRegisteredExpectation"] is True
    assert math_correct_over_limit["wrongAcceptance"] is False
    assert math_correct_over_limit["silentAcceptance"] is True


def test_template_saved_g_comes_from_protocol_parser() -> None:
    import sympy as sp
    from fractions import Fraction

    protocol = load_protocol()
    assert saved_g_source("canonical", protocol) == CANONICAL_G_SOURCE
    terms = parse_bivariate(saved_g_source("canonical", protocol))
    expr = sp.Integer(0)
    for (index_power, parameter_power), coefficient in terms.items():
        expr += (
            sp.Rational(int(coefficient.numerator), int(coefficient.denominator))
            * (_K ** index_power)
            * (_C ** parameter_power)
        )
    assert sp.expand(expr - CACHED_G) == 0
    assert parse_bivariate(saved_g_source("linear-k", protocol)) == {(1, 0): Fraction(1)}
    swapped = parse_bivariate(saved_g_source("swapped-cubes-antidifference", protocol))
    assert swapped[(4, 0)] == Fraction(1, 4)
    source = (ROOT / "research" / "trust_failclosed_eval" / "arms.py").read_text(encoding="utf-8")
    assert "_SAVED_G_EXPR" not in source
    assert "parse_bivariate" in source
    template_block = source.split("def run_p_pack")[0]
    assert "saved_g_source" in template_block


def test_pack_emitting_value_on_wrong_g_is_targeted_fix() -> None:
    scoring = score_cell(
        arm_id=ARM_P_PACK,
        task=task_by_id(TASK_WRONG_G),
        summary={"status": "ok", "valueExact": "6", "formalKernelChecked": False, "usedSavedContent": True},
        construction={"gosper_sum": 0, "construct_antidifference": 0, "summation": 0, "Sum.doit": 0},
    )
    assert scoring["trustworthiness"] == TRUST_SILENT_WRONG
    decision = decide(
        [
            {
                "arm": ARM_P_PACK,
                "task": TASK_WRONG_G,
                "scoring": scoring,
                "summary": {"valueExact": "6"},
            }
        ],
        stripped={"refused": True},
        binding={
            "packGoodResultBindingHolds": True,
            "packTamperedIdentityFailClosed": True,
            "templateHasObligationBindingHook": False,
        },
    )
    assert decision["verdict"] == "targeted_fix"
    assert decision["promote"] is False
    assert any("emitted a finite-sum value" in item for item in decision["problems"])


def test_contradicting_frozen_differentiation_clause_is_overwritten() -> None:
    frozen = load_protocol()["mandatoryClaimAnswerZh"]
    overwritten = reconcile_mandatory_claim_answer_zh(
        frozen,
        saved_g_differentiated=False,
        domain_differentiated=True,
    )
    assert overwritten["overwrittenBecauseDifferentiationFlagsDisagreed"] is True
    assert MANDATORY_CLAIM_NO_SAVED_G_DIFF_ZH in overwritten["answerZh"]
    assert MANDATORY_CLAIM_DIFFERENTIATION_ZH not in overwritten["answerZh"]
    consistent = reconcile_mandatory_claim_answer_zh(
        frozen,
        saved_g_differentiated=True,
        domain_differentiated=True,
    )
    assert consistent["overwrittenBecauseDifferentiationFlagsDisagreed"] is False
    assert MANDATORY_CLAIM_LATENCY_NOT_PRIMARY_ZH in consistent["answerZh"]


def test_cli_writes_report_and_refuses_overwrite(tmp_path: Path, report: dict) -> None:
    path = tmp_path / "trust-failclosed-report.json"
    write_report(path, report)
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored["kind"] == REPORT_KIND
    assert stored["decision"]["promote"] is False
    with pytest.raises(Exception, match="refusing to overwrite"):
        write_report(path, report)


def test_cli_end_to_end(tmp_path: Path) -> None:
    output = tmp_path / "trust-failclosed-report.json"
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
    assert stored["judgments"]["utility"]["verdict"] == "not_the_primary_claim"
    assert stored["decision"]["experimentVerdict"] == "differentiation_observed"
    assert stored["decision"]["promote"] is False
    wrong = next(
        cell
        for cell in stored["cells"]
        if cell["arm"] == ARM_P_PACK and cell["task"] == TASK_WRONG_G
    )
    assert wrong["scoring"]["trustworthiness"] == TRUST_FAIL_CLOSED
    template_wrong = next(
        cell
        for cell in stored["cells"]
        if cell["arm"] == ARM_B_TEMPLATE and cell["task"] == TASK_WRONG_G
    )
    assert template_wrong["summary"]["valueExact"] == WRONG_G_TEMPLATE_EXACT


def test_p_pack_used_saved_content_comes_from_apply() -> None:
    source = (ROOT / "research" / "trust_failclosed_eval" / "arms.py").read_text(encoding="utf-8")
    p_block = source.split("def run_p_pack")[1].split("def is_arm_exception")[0]
    assert 'wrapped["usedSavedContent"] = True' not in p_block
    result = run_p_pack(
        {
            "summand": "(k+3)^2",
            "variable": "k",
            "lower": 2,
            "upper": 7,
            "parameterC": "3",
            "taskId": "P1-shifted-square-c3-2-to-7",
            "savedG": "canonical",
        }
    )
    assert result["usedSavedContent"] is True
    assert result["status"] == "ok"
    assert result["value"]["exact"] == CONTROL_EXACT
