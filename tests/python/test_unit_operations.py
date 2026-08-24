from __future__ import annotations

import pytest

from math_anchor.catalog import search_operations
from math_anchor.errors import CalculatorError
from math_anchor.operations import units
from math_anchor.operations.data import _float_unit_registry
from math_anchor.operations.units import UNIT_CATALOG
from math_anchor.runtime import execute_direct


def test_stable_unit_catalog_is_searchable_and_runtime_backed() -> None:
    result = execute_direct("units.search", {"query": "Mbps"})
    assert result["count"] == 1
    assert result["units"] == [
        {
            "id": "megabit-per-second",
            "category": "data_rate",
            "name": "Megabits per second",
            "symbol": "Mbit/s",
            "runtimeUnit": "megabit / second",
        }
    ]

    torque = execute_direct("units.search", {"category": "torque"})
    assert [unit["id"] for unit in torque["units"]] == [
        "newton-meter",
        "pound-force-foot",
    ]
    assert search_operations("查找单位")["operations"][0]["id"] == "units.search"

    registry = _float_unit_registry()
    for unit in UNIT_CATALOG:
        registry.parse_units(unit.runtime_unit)


def test_stable_ids_cover_data_rates_and_engineering_quantities() -> None:
    si_data = execute_direct(
        "units.convert",
        {"value": 1, "fromUnit": "gigabyte", "toUnit": "byte"},
    )
    assert si_data["exact"] == "1000000000"

    binary_data = execute_direct(
        "units.convert",
        {"value": 1, "fromUnit": "gibibyte", "toUnit": "byte"},
    )
    assert binary_data["exact"] == "1073741824"

    data_rate = execute_direct(
        "units.convert",
        {"value": "100", "fromUnit": "megabit-per-second", "toUnit": "megabyte-per-second"},
    )
    assert data_rate["exact"] == "25/2"

    density = execute_direct(
        "units.convert",
        {"value": 1, "fromUnit": "gram-per-cubic-centimeter", "toUnit": "kilogram-per-cubic-meter"},
    )
    assert density["exact"] == "1000"

    acceleration = execute_direct(
        "units.convert",
        {"value": 1, "fromUnit": "standard-gravity", "toUnit": "meter-per-second-squared"},
    )
    assert acceleration["exact"] == "196133/20000"

    torque = execute_direct(
        "units.convert",
        {"value": 1, "fromUnit": "newton-meter", "toUnit": "pound-force-foot"},
    )
    assert torque["exact"] is not None
    assert torque["approx"].startswith("0.73756")


def test_calendar_durations_require_an_explicit_average_convention() -> None:
    for arguments in (
        {"value": 1, "fromUnit": "month", "toUnit": "day"},
        {"value": 1, "fromUnit": "year", "toUnit": "day"},
    ):
        with pytest.raises(CalculatorError) as raised:
            execute_direct("units.convert", arguments)
        assert raised.value.code == "E_UNIT"
        assert "calendarPolicy='average_duration'" in raised.value.message

    month = execute_direct(
        "units.convert",
        {
            "value": 1,
            "fromUnit": "month",
            "toUnit": "day",
            "calendarPolicy": "average_duration",
        },
    )
    assert month["exact"] == "487/16"
    assert "not date or time-zone arithmetic" in month["warnings"][0]

    with pytest.raises(CalculatorError) as expression_rejected:
        execute_direct(
            "quantity.evaluate",
            {"expression": "1 * year", "toUnit": "day"},
        )
    assert expression_rejected.value.code == "E_UNIT"

    expression = execute_direct(
        "quantity.evaluate",
        {
            "expression": "1 * year",
            "toUnit": "day",
            "calendarPolicy": "average_duration",
        },
    )
    assert expression["exact"] == "1461/4"
    assert "civil-calendar concepts" in expression["warnings"][0]


@pytest.mark.parametrize(
    ("arguments", "code"),
    [
        ({"category": "currency"}, "E_INPUT"),
        ({"limit": 51}, "E_LIMIT"),
        ({"query": "x" * 129}, "E_LIMIT"),
        ({"query": 5}, "E_INPUT"),
        ({"query": "meter", "extra": True}, "E_INPUT"),
    ],
)
def test_unit_search_rejects_out_of_contract_requests(
    arguments: dict[str, object],
    code: str,
) -> None:
    with pytest.raises(CalculatorError) as raised:
        execute_direct("units.search", arguments)
    assert raised.value.code == code


def test_calendar_verification_fails_closed_when_introspection_breaks() -> None:
    class OpaqueUnit:
        # Simulates a Pint upgrade moving the private _units layout: when
        # calendar membership can no longer be verified, the runtime must
        # reject rather than let month/year silently convert.
        pass

    with pytest.raises(CalculatorError) as raised:
        units.calendar_unit_names(OpaqueUnit())
    assert raised.value.code == "E_UNIT"


def test_unit_search_handler_rejects_unknown_category_directly() -> None:
    with pytest.raises(CalculatorError) as raised:
        units.search({"query": "hz", "category": "velocity"})
    assert raised.value.code == "E_INPUT"
