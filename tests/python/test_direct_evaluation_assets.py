from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[2]
DIRECT_DIR = ROOT / "evals" / "direct"
DRIVER = ROOT / "script" / "direct_eval_driver.py"


def _load(name: str) -> dict:
    return json.loads((DIRECT_DIR / name).read_text(encoding="utf-8"))


def _request(operation: str, arguments: dict) -> dict:
    return {
        "schemaVersion": "openadam.agent-tool-eval.direct-driver-request.v0.1",
        "executionMode": "direct-host",
        "runId": "math-anchor.direct-host.test:r1",
        "task": {
            "id": "math-anchor.direct-host.test",
            "invocation": {
                "operationId": "math.run",
                "input": {"operation": operation, "arguments": arguments},
            },
            "tags": ["test"],
        },
        "purpose": "development-smoke",
        "repeat": 1,
        "target": {"id": "math-anchor", "version": "0.5.0"},
        "providerRef": {"id": "math-anchor-local-runtime", "version": "0.5.0"},
        "driverRef": {"id": "math-anchor-direct-driver", "version": "0.1.0"},
        "budget": {"timeoutMs": 10000},
        "isolation": {"mode": "deny-read-roots", "deniedReadRoots": ["/private/tmp/oracle"]},
    }


def _invoke(request: dict) -> subprocess.CompletedProcess[str]:
    virtual_bin = ROOT / ".venv" / "bin"
    environment = {**os.environ, "PATH": f"{virtual_bin}{os.pathsep}{os.environ.get('PATH', '')}"}
    return subprocess.run(
        [str(DRIVER)],
        input=json.dumps(request),
        text=True,
        capture_output=True,
        env=environment,
        check=False,
        timeout=20,
    )


def test_direct_host_assets_are_separate_structured_zero_model_inputs() -> None:
    suite = _load("coding-agent-profile.v0.1.json")
    plan = _load("math-anchor-cold-smoke.v0.1.json")
    assert suite["executionMode"] == plan["executionMode"] == "direct-host"
    assert suite["targetRef"] == plan["targetRef"] == {"id": "math-anchor", "version": "0.5.0"}
    assert plan["purpose"] == "development-smoke"
    assert plan["repeats"] == 1
    assert plan["driver"]["root"] == "/MATH_ANCHOR_ROOT"
    assert plan["driver"]["command"] == "/MATH_ANCHOR_DIRECT_DRIVER"
    assert len(suite["tasks"]) == 13
    serialized = json.dumps({"suite": suite, "plan": plan}).lower()
    for forbidden in ("agent", "harness", "prompt", "token", "treatment", "baseline"):
        assert f'"{forbidden}"' not in serialized
    assert all(task["invocation"]["operationId"] == "math.run" for task in suite["tasks"])
    assert all(set(task["invocation"]["input"]) == {"operation", "arguments"} for task in suite["tasks"])


def test_direct_driver_returns_a_typed_math_anchor_result_with_runtime_identity() -> None:
    completed = _invoke(
        _request(
            "integer.machine_arithmetic",
            {
                "action": "add",
                "left": "250",
                "right": "20",
                "bitWidth": 8,
                "signedness": "unsigned",
                "inputMode": "value",
                "overflowBehavior": "wrapping",
            },
        )
    )
    assert completed.returncode == 0, completed.stderr
    response = json.loads(completed.stdout)
    assert response["executionMode"] == "direct-host"
    assert response["status"] == "success"
    assert response["answer"]["result"]["decimal"] == "14"
    assert response["runtime"] == {
        "driver": {"id": "math-anchor-direct-driver", "version": "0.1.0"},
        "provider": {"id": "math-anchor-local-runtime", "version": "0.5.0"},
        "target": {"id": "math-anchor", "version": "0.5.0"},
    }


def test_direct_driver_preserves_provider_errors_as_ungraded_error_results() -> None:
    completed = _invoke(_request("expression.evaluate", {"expression": "missing_symbol + 1"}))
    assert completed.returncode == 0, completed.stderr
    response = json.loads(completed.stdout)
    assert response["status"] == "error"
    assert response["error"]["code"] == "E_NAME"
    assert response["error"]["retryable"] is False
    assert "answer" not in response
