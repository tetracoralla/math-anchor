"""Honesty tests for the Epoch 2 shadow-verifier scaffold.

Green tests here record the pinned protocol, B2/B3 fail-closed detection,
quiet-success / failures_only semantics, and that B0/B1 stay deferred.
They are not completion of Epoch 2 and not a promotion claim.
Do not invent live-model numbers or a savings percentage.
"""

from __future__ import annotations

from copy import deepcopy
import ast
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research.shadow_verifier_eval.arms import run_b2, run_b3
from research.shadow_verifier_eval.model_interface import (
    ModelArmDeferredError,
    model_arm_contract,
    reject_include_model_arms,
)
from research.shadow_verifier_eval.protocol import (
    ALL_TASKS,
    ARM_B0,
    ARM_B1,
    ARM_B2,
    ARM_B3,
    CONTROL_TASKS,
    CORRUPTION_KIND_IDS,
    DEFERRED_ARMS,
    GATE_IDS,
    MCP_TOOLS,
    MODEL_ARMS_DEFERRED,
    PRIMARY_ARMS,
    PROTOCOL_KIND,
    REPORT_KIND,
    RUNNABLE_ARMS,
    SUPPORTED_ERROR_TASKS,
    TASK_CONTROL_POLY,
    TASK_DEPENDENCY,
    TASK_DIMENSION_MISMATCH,
    TASK_DOMAIN_OVERSHOOT,
    TASK_SIGN_FLIP,
    TASK_UNSUPPORTED,
    load_protocol,
    protocol_digest,
    validate_protocol,
)
from research.shadow_verifier_eval.smoke import run_smoke, write_report


RUNNER = ROOT / "research" / "shadow_verifier_eval" / "run.py"
HARNESS_FILES = (
    ROOT / "research" / "shadow_verifier_eval" / "protocol.py",
    ROOT / "research" / "shadow_verifier_eval" / "arms.py",
    ROOT / "research" / "shadow_verifier_eval" / "probes.py",
    ROOT / "research" / "shadow_verifier_eval" / "score.py",
    ROOT / "research" / "shadow_verifier_eval" / "smoke.py",
    ROOT / "research" / "shadow_verifier_eval" / "run.py",
    ROOT / "research" / "shadow_verifier_eval" / "model_interface.py",
)


@pytest.fixture(scope="module")
def report() -> dict:
    return run_smoke()


def _cell(report: dict, arm: str, task: str) -> dict:
    for cell in report["cells"]:
        if cell["arm"] == arm and cell["task"] == task:
            return cell
    raise AssertionError(f"missing cell {arm}×{task}")


def test_protocol_is_pre_registered_with_four_arms_and_gates() -> None:
    protocol = load_protocol()
    assert protocol["kind"] == PROTOCOL_KIND
    assert protocol["preRegistered"] is True
    assert protocol["promotionForbiddenInThisSmoke"] is True
    assert protocol["epoch2NotCompleteUntilLiveFourArmEvidence"] is True
    assert protocol["doNotStartH1"] is True
    assert protocol["doNotPromoteMethodPacks"] is True
    assert protocol["model"]["callsAllowed"] is False
    assert protocol["model"]["modelArms"] == MODEL_ARMS_DEFERRED
    assert protocol["budget"]["dollarCosts"] is None
    assert protocol["budget"]["modelCalls"] == 0
    assert [arm["id"] for arm in protocol["arms"]] == list(PRIMARY_ARMS)
    assert [task["id"] for task in protocol["tasks"]] == list(ALL_TASKS)
    assert tuple(protocol["gates"]) == GATE_IDS
    assert tuple(protocol["corruptionKinds"]) == CORRUPTION_KIND_IDS
    b0 = next(arm for arm in protocol["arms"] if arm["id"] == ARM_B0)
    b1 = next(arm for arm in protocol["arms"] if arm["id"] == ARM_B1)
    b2 = next(arm for arm in protocol["arms"] if arm["id"] == ARM_B2)
    b3 = next(arm for arm in protocol["arms"] if arm["id"] == ARM_B3)
    assert b0["runnableThisSmoke"] is False
    assert b1["runnableThisSmoke"] is False
    assert b1["mcpTools"] == list(MCP_TOOLS)
    assert b1["fifthMcpTool"] is False
    assert b2["runnableThisSmoke"] is True
    assert b2["responseMode"] == "full"
    assert b3["runnableThisSmoke"] is True
    assert b3["responseMode"] == "failures_only"
    assert b3["quietSuccess"] is True
    assert b3["repairHookIsNotLiveModelRepair"] is True
    assert protocol["honesty"]["polynomialCheckerIndependenceIsNotEveryKind"] is True
    assert protocol["honesty"]["calculatorIsNotStandingBanned"] is True
    assert protocol["honesty"]["b3LibraryQuietSuccessZeroBytesIsWrapperProjection"] is True
    assert protocol["honesty"]["productQuietSuccessEvidenceIsCliStdout"] is True
    assert protocol["honesty"]["seededRepairProbeIsSameClaimCorrectionOnly"] is True
    assert protocol["honesty"]["dimensionMismatchResubmitIsNotOriginalClaimRepair"] is True
    assert b2["receiptOutsideModelContext"] is False
    assert b3["receiptOutsideModelContext"] is True


def test_unsupported_protocol_overrides_are_rejected() -> None:
    original = load_protocol()
    only_b2 = deepcopy(original)
    only_b2["arms"] = [arm for arm in only_b2["arms"] if arm["id"] == ARM_B2]
    with pytest.raises(ValueError, match="pre-registered"):
        validate_protocol(only_b2)
    with pytest.raises(ValueError, match="pre-registered"):
        run_smoke(protocol=only_b2)

    mutated_task = deepcopy(original)
    mutated_task["tasks"][0]["expectedPrimaryStatus"] = "falsified"
    with pytest.raises(ValueError, match="pre-registered"):
        validate_protocol(mutated_task)

    mutated_gates = deepcopy(original)
    mutated_gates["gates"] = {**mutated_gates["gates"], "G1": {**mutated_gates["gates"]["G1"], "status": "met"}}
    with pytest.raises(ValueError, match="pre-registered"):
        validate_protocol(mutated_gates)

    mutated_model = deepcopy(original)
    mutated_model["model"] = {**mutated_model["model"], "modelArms": "ran"}
    with pytest.raises(ValueError, match="model_arms=deferred"):
        validate_protocol(mutated_model)

    mutated_honesty = deepcopy(original)
    mutated_honesty["honesty"] = {**mutated_honesty["honesty"], "formalKernelChecked": True}
    with pytest.raises(ValueError, match="pre-registered honesty"):
        validate_protocol(mutated_honesty)

    mutated_live = deepcopy(original)
    mutated_live["liveModelCommands"] = {
        **mutated_live["liveModelCommands"],
        "plannedLiveFourArm": "invented",
    }
    with pytest.raises(ValueError, match="pre-registered liveModelCommands"):
        validate_protocol(mutated_live)

    mutated_budget = deepcopy(original)
    mutated_budget["budget"] = {**mutated_budget["budget"], "modelCalls": 999}
    with pytest.raises(ValueError, match="pre-registered budget"):
        validate_protocol(mutated_budget)
    with pytest.raises(ValueError, match="pre-registered budget"):
        run_smoke(protocol=mutated_budget)


def test_b2_b3_detect_supported_seeded_errors(report: dict) -> None:
    expected_status = {
        TASK_SIGN_FLIP: "falsified",
        TASK_DOMAIN_OVERSHOOT: "falsified",
        TASK_DIMENSION_MISMATCH: "falsified",
    }
    for task_id, status in expected_status.items():
        for arm in RUNNABLE_ARMS:
            cell = _cell(report, arm, task_id)
            assert cell["primaryStatus"] == status
            assert cell["detected"] is True
            assert cell["scoring"]["matchedPreRegisteredExpectation"] is True
            assert cell["scoring"]["g1SupportedSeededError"] is True
            assert cell["coversOriginalTaskClaim"] is False
            assert cell["formalKernelChecked"] is False


def test_b2_b3_controls_are_checked_not_false_reject(report: dict) -> None:
    for task_id in CONTROL_TASKS:
        for arm in RUNNABLE_ARMS:
            cell = _cell(report, arm, task_id)
            assert cell["primaryStatus"] == "checked"
            assert cell["feedbackStatus"] == "checked"
            assert cell["scoring"]["falseReject"] is not True
            assert cell["scoring"]["matchedPreRegisteredExpectation"] is True


def test_b3_quiet_success_returns_zero_model_context(report: dict) -> None:
    for task_id in CONTROL_TASKS:
        cell = _cell(report, ARM_B3, task_id)
        assert cell["quietSuccess"] is True
        assert cell["modelContextBytes"] == 0
        assert cell["returnedFeedback"] is None
        assert cell["receiptOutsideModelContext"] is True
        assert cell["feedbackIncludesPrimary"] is False
        assert cell["receiptBytes"] > 0
        assert int(cell["runtimeFeedbackBytes"] or 0) > 0
        assert cell["modelContextBytesIsWrapperProjection"] is True
        b2 = _cell(report, ARM_B2, task_id)
        assert b2["quietSuccess"] is False
        assert b2["feedbackIncludesPrimary"] is True
        assert int(b2["modelContextBytes"] or 0) > 0
        assert b2["receiptOutsideModelContext"] is False
        assert b2["receiptPath"] is not None
        assert b2["modelContextBytesIsWrapperProjection"] is False


def test_b2_receipt_outside_model_context_follows_arm_semantics(report: dict) -> None:
    for task_id in ALL_TASKS:
        b2 = _cell(report, ARM_B2, task_id)
        b3 = _cell(report, ARM_B3, task_id)
        assert b2["receiptOutsideModelContext"] is False
        assert b2["scoring"]["receiptOutsideModelContext"] is False
        assert b2["receiptPath"] is not None
        assert b2["returnedFeedback"] is not None
        assert b3["receiptOutsideModelContext"] is True
        assert b3["scoring"]["receiptOutsideModelContext"] is True
    control = next(task for task in load_protocol()["tasks"] if task["id"] == TASK_CONTROL_POLY)
    without_file = run_b2(control)
    assert without_file["receiptPath"] is None
    assert without_file["receiptOutsideModelContext"] is False


def test_b3_failures_only_on_seeded_errors(report: dict) -> None:
    cell = _cell(report, ARM_B3, TASK_SIGN_FLIP)
    assert cell["quietSuccess"] is False
    assert cell["feedbackStatus"] == "attention_required"
    assert cell["feedbackIncludesPrimary"] is True
    assert int(cell["modelContextBytes"] or 0) > 0
    assert cell["receiptOutsideModelContext"] is True


def test_b3_seeded_repair_hook_is_not_live_model_repair(report: dict) -> None:
    sign_flip = _cell(report, ARM_B3, TASK_SIGN_FLIP)
    repair = sign_flip["repair"]
    assert repair["notALiveModelRepair"] is True
    assert repair["kind"] == "same_claim_correction"
    assert repair["sameClaimCorrection"] is True
    assert repair["primaryStatus"] == "checked"
    assert repair["quietSuccess"] is True
    assert sign_flip["scoring"]["repairMatched"] is True
    assert sign_flip["scoring"]["sameClaimCorrection"] is True
    assert _cell(report, ARM_B2, TASK_SIGN_FLIP).get("repair") is None

    dimension = _cell(report, ARM_B3, TASK_DIMENSION_MISMATCH)
    resubmit = dimension["repair"]
    assert resubmit["notALiveModelRepair"] is True
    assert resubmit["kind"] == "unrelated_valid_resubmit"
    assert resubmit["sameClaimCorrection"] is False
    assert resubmit["primaryStatus"] == "checked"
    assert dimension["scoring"]["repairMatched"] is None
    assert dimension["scoring"]["unrelatedValidResubmitMatched"] is True
    assert dimension["scoring"]["sameClaimCorrection"] is False
    assert _cell(report, ARM_B2, TASK_DIMENSION_MISMATCH).get("repair") is None


def test_completeness_unsupported_and_dependency_blocked(report: dict) -> None:
    unsupported = _cell(report, ARM_B2, TASK_UNSUPPORTED)
    assert unsupported["primaryStatus"] == "unsupported"
    blocked = _cell(report, ARM_B3, TASK_DEPENDENCY)
    assert blocked["primaryStatus"] == "unknown"
    statuses = {item["id"]: item["status"] for item in blocked["obligationSummaries"]}
    assert statuses["sheaf-step"] == "unsupported"
    assert statuses["dependent-step"] == "unknown"


def test_b0_b1_are_deferred_without_invented_model_numbers(report: dict) -> None:
    for arm in DEFERRED_ARMS:
        for task_id in ALL_TASKS:
            cell = _cell(report, arm, task_id)
            assert cell["status"] == MODEL_ARMS_DEFERRED
            assert cell["modelArms"] == MODEL_ARMS_DEFERRED
            assert cell["liveQualityDelta"] is None
            assert cell["finalAccuracy"] is None
            assert cell["acceptedSeededError"] is None
            assert cell["runnableThisSmoke"] is False
            assert isinstance(cell.get("prompt"), str) and cell["prompt"]
    b1 = model_arm_contract(ARM_B1)
    assert b1["mcpTools"] == list(MCP_TOOLS)
    assert b1["fifthMcpTool"] is False
    assert b1["correctAnswerWithoutTargetCallIsNotAdoption"] is True
    blob = json.dumps(report)
    assert "usd" not in blob.lower()
    assert report["refusedClaims"]["liveModelQualityDelta"]["emitted"] is False


def test_structural_probes_reuse_obligation_binding_and_cli(report: dict) -> None:
    probes = report["structuralProbes"]
    assert probes["ok"] is True
    core = probes["coreConformance"]
    assert core["ok"] is True
    assert core["exercisedChecked"] is True
    assert core["exercisedFalsified"] is True
    assert core["exercisedUnsupported"] is True
    assert core["exercisedDependencyBlocked"] is True
    assert core["failuresOnlyLeakedChecked"] is False
    wrong = probes["wrongWitness"]
    assert wrong["failClosed"] is True
    assert wrong["status"] == "unknown"
    assert wrong["reason"] == "certificate_rejected"
    assert wrong["checked"] is False
    stale = probes["staleSwappedResult"]
    assert stale["failClosed"] is True
    assert stale["status"] == "unknown"
    quiet = probes["cliQuietSuccess"]
    assert quiet["stdoutEmpty"] is True
    assert quiet["stdoutBytes"] == 0
    assert quiet["receiptExists"] is True
    failure = probes["cliFailuresOnlyOnFail"]
    assert failure["ok"] is True
    assert failure["exitCode"] == 1
    assert failure["obligationIds"] == ["sign-flip"]


def test_gates_remain_targets_and_epoch2_is_not_complete(report: dict) -> None:
    gates = report["gates"]
    assert gates["allRemainTargets"] is True
    assert tuple(gates["ids"]) == GATE_IDS
    for gate_id in GATE_IDS:
        assert gates[gate_id]["epoch2GateMet"] is False
        assert gates[gate_id]["status"] in {"target", "target-deferred"}
    g1 = gates["G1"]["thisMachine"]
    assert g1["B2"]["detected"] == g1["B2"]["total"] == 3
    assert g1["B3"]["detected"] == g1["B3"]["total"] == 3
    assert g1["bindingProbes"]["detected"] == 2
    assert gates["G1"]["thisMachineDoesNotMeetEpoch2Gate"] is True
    assert gates["G2"]["thisMachine"] is None
    assert gates["G3"]["thisMachine"]["B2FalseRejects"] == 0
    assert gates["G3"]["thisMachine"]["B3FalseRejects"] == 0
    assert gates["G4"]["thisMachine"]["B3QuietSuccessZeroReturnedContent"] is True
    assert gates["G4"]["thisMachine"]["B3LibraryZeroBytesIsWrapperProjection"] is True
    assert gates["G4"]["thisMachine"]["productEvidenceCliQuietSuccessStdoutEmpty"] is True
    assert gates["G4"]["thisMachine"]["tenPercentVsB0"] is None
    assert gates["G5"]["thisMachine"]["B3SameClaimSeededCorrectionMatched"] is True
    assert gates["G5"]["thisMachine"]["B3SeededRepairHookMatched"] is True
    assert gates["G5"]["thisMachine"]["B3UnrelatedValidResubmitReachedChecked"] is True
    assert gates["G5"]["thisMachine"]["dimensionMismatchResubmitIsNotOriginalClaimRepair"] is True
    assert gates["G5"]["thisMachine"]["notALiveModelRepair"] is True
    assert gates["G5"]["epoch2GateMet"] is False
    assert gates["G5"]["thisMachineDoesNotMeetEpoch2Gate"] is True
    assert gates["G6"]["thisMachine"] is None
    decision = report["decision"]
    assert decision["promote"] is False
    assert decision["publicPromotion"] is False
    assert decision["doNotStartH1"] is True
    assert decision["epoch2Complete"] is False
    assert decision["modelArms"] == MODEL_ARMS_DEFERRED
    assert decision["verdict"] == "evidence_insufficient"
    assert decision["experimentVerdict"] == "deterministic_b2_b3_scaffold_ran"
    assert decision["targetedFix"] is False
    assert report["kind"] == REPORT_KIND
    assert report["protocolDigest"] == protocol_digest()
    assert report["honesty"]["epoch2NotCompleteUntilLiveFourArmEvidence"] is True
    assert report["honesty"]["b3LibraryQuietSuccessZeroBytesIsWrapperProjection"] is True
    assert report["honesty"]["productQuietSuccessEvidenceIsCliStdout"] is True
    assert report["honesty"]["seededRepairProbeIsSameClaimCorrectionOnly"] is True


def test_include_model_arms_is_rejected() -> None:
    with pytest.raises(ModelArmDeferredError, match="model_arms=deferred"):
        reject_include_model_arms()
    with pytest.raises(ModelArmDeferredError, match="model_arms=deferred"):
        run_smoke(include_model_arms=True)
    completed = subprocess.run(
        [sys.executable, str(RUNNER), "--include-model-arms"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 2
    payload = json.loads(completed.stdout)
    assert payload["error"]["code"] == "E_INPUT"
    assert "deferred" in payload["error"]["message"]


def test_report_refuses_overwrite_and_benefit_percent(report: dict, tmp_path: Path) -> None:
    path = tmp_path / "shadow-verifier-report.json"
    write_report(path, report)
    with pytest.raises(Exception, match="refusing to overwrite"):
        write_report(path, report)
    assert report["refusedClaims"]["overallBenefitPercent"]["emitted"] is False
    assert report["refusedClaims"]["savingsPercent"]["emitted"] is False
    assert report["refusedClaims"]["dollarCosts"]["emitted"] is False
    blob = json.dumps(report)
    assert "$" not in blob
    assert "savings %" not in blob.lower()


def test_b2_b3_call_existing_obligation_runtime_not_a_second_stack() -> None:
    source = (ROOT / "research" / "shadow_verifier_eval" / "arms.py").read_text(encoding="utf-8")
    assert "check_obligation_set" in source
    assert "from math_anchor.obligations import check_obligation_set" in source
    assert "def check_obligation_set" not in source
    b2_src = (ROOT / "research" / "shadow_verifier_eval" / "arms.py").read_text(encoding="utf-8")
    tree = ast.parse(b2_src)
    collected: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            collected.add(node.id)
    assert "eval" not in collected
    assert "exec" not in collected
    control = next(task for task in load_protocol()["tasks"] if task["id"] == TASK_CONTROL_POLY)
    result = run_b2(control)
    assert result["engine"] == "math-anchor.obligation-set.v0.1"
    assert result["notASecondStack"] is True
    assert result["primaryStatus"] == "checked"


def test_harness_source_does_not_hardcode_savings_or_live_deltas() -> None:
    for path in HARNESS_FILES:
        text = path.read_text(encoding="utf-8")
        lowered = text.lower()
        assert "savings %" not in lowered
        assert "usd" not in lowered
        assert "quality_delta =" not in lowered


def test_independence_statement_is_honest(report: dict) -> None:
    independence = report["independence"]
    assert "stdlib" in independence["polynomialIdentityChecker"]
    assert "not a second checker stack" in independence["otherKinds"]
    assert "context isolation" in independence["shadowCheckpoint"]
    assert "surrounding prose" in independence["producerVsChecker"]
    assert report["progressiveAssurance"] == [
        "Claim",
        "Certificate/Witness",
        "Independent Verifier",
        "Binding",
        "Assurance",
        "Receipt",
    ]


def test_runner_exit_zero_on_scaffold_success(tmp_path: Path) -> None:
    output = tmp_path / "report.json"
    completed = subprocess.run(
        [sys.executable, str(RUNNER), "--output", str(output), "--receipt-dir", str(tmp_path / "receipts")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["decision"]["promote"] is False
    assert payload["decision"]["epoch2Complete"] is False
    assert output.is_file()
    assert (tmp_path / "receipts" / "B3-control-polynomial-identity.receipt.json").is_file()
