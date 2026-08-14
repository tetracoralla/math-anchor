from zibetha import app_runtime


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
