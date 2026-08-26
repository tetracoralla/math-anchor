import threading
import time

from math_anchor import app_runtime


def test_expression_request_remains_backward_compatible() -> None:
    response = app_runtime._handle(
        {"id": "expression-1", "expression": "6*7", "precision": 16}
    )

    assert response["id"] == "expression-1"
    assert response["status"] == "ok"
    assert response["exact"] == "42"


def test_unit_conversion_uses_the_existing_units_core() -> None:
    response = app_runtime._handle(
        {
            "id": "conversion-1",
            "operation": "units.convert",
            "value": "1",
            "fromUnit": "meter",
            "toUnit": "foot",
            "precision": 12,
        }
    )

    assert response["id"] == "conversion-1"
    assert response["status"] == "ok"
    assert response["operation"] == "units.convert"
    assert response["exact"] == "1250/381"
    assert response["unit"] == "ft"


def test_unit_conversion_accepts_stable_engineering_unit_ids() -> None:
    response = app_runtime._handle(
        {
            "id": "conversion-data-rate",
            "operation": "units.convert",
            "value": "100",
            "fromUnit": "megabit-per-second",
            "toUnit": "megabyte-per-second",
            "precision": 12,
        }
    )

    assert response["id"] == "conversion-data-rate"
    assert response["status"] == "ok"
    assert response["exact"] == "25/2"
    assert response["unit"] == "MB / s"


def test_incompatible_unit_conversion_is_a_bounded_error() -> None:
    response = app_runtime._handle(
        {
            "id": "conversion-error",
            "operation": "units.convert",
            "value": "1",
            "fromUnit": "meter",
            "toUnit": "kilogram",
        }
    )

    assert response["id"] == "conversion-error"
    assert response["status"] == "error"
    assert response["error"]["code"] == "E_UNIT"


def test_unknown_app_operation_preserves_request_id() -> None:
    response = app_runtime._handle(
        {"id": "unknown-1", "operation": "unknown.operation"}
    )

    assert response["id"] == "unknown-1"
    assert response["status"] == "error"
    assert response["error"]["code"] == "E_OPERATION"


def test_currency_request_uses_the_app_provider_contract(monkeypatch) -> None:
    received = {}
    precision_resets = []

    def convert(arguments, *, service):
        assert service is app_runtime._CURRENCY_SERVICE
        received.update(arguments)
        return {
            "status": "ok",
            "operation": "currency.convert",
            "kind": "currency",
            "exact": None,
            "approx": "14.82",
            "precision": 12,
            "unit": "USD",
            "rate": {"state": "current"},
            "warnings": [],
        }

    monkeypatch.setattr(app_runtime, "currency_convert", convert)
    monkeypatch.setattr(
        app_runtime,
        "ensure_mpmath_default_precision",
        lambda: precision_resets.append(True),
    )
    response = app_runtime._handle(
        {
            "id": "currency-1",
            "operation": "currency.convert",
            "value": "100",
            "fromCurrency": "CNY",
            "toCurrency": "USD",
            "precision": 12,
            "forceRefresh": True,
        }
    )

    assert response["id"] == "currency-1"
    assert response["status"] == "ok"
    assert response["approx"] == "14.82"
    assert precision_resets == []
    assert received == {
        "value": "100",
        "fromCurrency": "CNY",
        "toCurrency": "USD",
        "precision": 12,
        "forceRefresh": True,
    }


def test_unexpected_app_runtime_error_preserves_request_id(monkeypatch) -> None:
    def fail(_arguments):
        raise ValueError("serialization failed")

    monkeypatch.setattr(app_runtime, "evaluate", fail)
    response = app_runtime._handle(
        {"id": "request-123", "expression": "factorial(5000)", "precision": 16}
    )

    assert response["id"] == "request-123"
    assert response["status"] == "error"
    assert response["error"]["code"] == "E_RUNTIME"


def test_currency_request_does_not_block_local_operations(monkeypatch) -> None:
    release = threading.Event()

    def blocking_currency_convert(_arguments, *, service):
        assert release.wait(timeout=5)
        return {
            "status": "ok",
            "operation": "currency.convert",
            "kind": "currency",
            "exact": None,
            "approx": "1",
            "precision": 12,
            "unit": "EUR",
            "rate": {"state": "current"},
            "warnings": [],
        }

    class LockedBuffer:
        def __init__(self) -> None:
            self._lock = threading.Lock()
            self._text = ""

        def write(self, value: str) -> int:
            with self._lock:
                self._text += value
            return len(value)

        def flush(self) -> None:
            return None

        @property
        def text(self) -> str:
            with self._lock:
                return self._text

    monkeypatch.setattr(app_runtime, "currency_convert", blocking_currency_convert)
    buffer = LockedBuffer()
    monkeypatch.setattr(app_runtime.sys, "stdout", buffer)

    class PipelinedStdin:
        def __iter__(self):
            yield '{"id":"currency-slow","operation":"currency.convert","value":"1","fromCurrency":"USD","toCurrency":"EUR"}\n'
            yield '{"id":"evaluate-fast","expression":"6*7","precision":16}\n'

    monkeypatch.setattr(app_runtime.sys, "stdin", PipelinedStdin())
    app_runtime.main()

    # The local expression must be answered while the currency request is
    # still waiting on its provider fetch.
    lines_before_release = [line for line in buffer.text.splitlines() if line]
    assert lines_before_release[0] == '{"status":"ready"}'
    assert '"id":"evaluate-fast"' in lines_before_release[1]
    assert '"exact":"42"' in lines_before_release[1]
    assert all('"currency-slow"' not in line for line in lines_before_release)

    release.set()
    deadline = time.monotonic() + 5
    currency_line = None
    while time.monotonic() < deadline:
        lines = [line for line in buffer.text.splitlines() if '"currency-slow"' in line]
        if lines:
            currency_line = lines[0]
            break
        time.sleep(0.01)
    assert currency_line is not None
    assert '"status":"ok"' in currency_line
