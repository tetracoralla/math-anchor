from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import threading

import pytest

from math_anchor.currency import ECBRateService
from math_anchor.errors import CalculatorError


NOW = datetime(2026, 8, 13, 11, 15, tzinfo=timezone.utc)
RATES = {
    "USD": "1.20",
    "JPY": "180",
    "CZK": "24",
    "DKK": "7.4",
    "GBP": "0.85",
    "HUF": "365",
    "PLN": "4.3",
    "RON": "5.2",
    "SEK": "11",
    "CHF": "0.94",
    "ISK": "142",
    "NOK": "10.9",
    "TRY": "55",
    "AUD": "1.63",
    "BRL": "5.95",
    "CAD": "1.61",
    "CNY": "7.20",
    "HKD": "9.05",
    "IDR": "20500",
    "ILS": "3.45",
    "INR": "110",
    "KRW": "1630",
    "MXN": "19.7",
    "MYR": "4.7",
    "NZD": "1.96",
    "PHP": "70.6",
    "SGD": "1.47",
    "THB": "38.1",
    "ZAR": "18.6",
}


class FakeResponse:
    def __init__(self, body: bytes, *, last_modified: str | None = None) -> None:
        self.body = body
        self.headers = {"Last-Modified": last_modified} if last_modified else {}

    def __enter__(self):
        return self

    def __exit__(self, _type, _value, _traceback) -> None:
        return None

    def read(self, _limit: int) -> bytes:
        return self.body


def xml_rates(rates: dict[str, str] = RATES) -> bytes:
    rows = "".join(
        f'<Cube currency="{currency}" rate="{rate}"/>'
        for currency, rate in rates.items()
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Envelope><Cube><Cube time="2026-08-12">'
        f"{rows}"
        "</Cube></Cube></Envelope>"
    ).encode()


def response_opener(body: bytes = xml_rates(), *, calls: list[str] | None = None):
    def open_response(request, *, timeout):
        if calls is not None:
            calls.append(request.full_url)
        assert timeout == 4.0
        return FakeResponse(body, last_modified="Wed, 12 Aug 2026 13:56:24 GMT")

    return open_response


def failing_opener(_request, *, timeout):
    assert timeout == 4.0
    raise OSError("network is offline")


def conversion_arguments(**overrides):
    arguments = {
        "value": "10",
        "fromCurrency": "USD",
        "toCurrency": "CNY",
        "precision": 12,
    }
    arguments.update(overrides)
    return arguments


def test_currency_conversion_fetches_ecb_rates_and_persists_metadata(tmp_path: Path) -> None:
    calls: list[str] = []
    cache_path = tmp_path / "rates.json"
    service = ECBRateService(
        cache_path=cache_path,
        opener=response_opener(calls=calls),
        clock=lambda: NOW,
    )

    result = service.convert(conversion_arguments())

    assert result["status"] == "ok"
    assert result["operation"] == "currency.convert"
    assert result["exact"] is None
    assert result["approx"] == "60"
    assert result["unit"] == "CNY"
    assert result["rate"] == {
        "sourceName": "European Central Bank",
        "sourceShortName": "ECB",
        "sourceURL": (
            "https://www.ecb.europa.eu/stats/policy_and_exchange_rates/"
            "euro_reference_exchange_rates/html/index.en.html"
        ),
        "rateDate": "2026-08-12",
        "publishedAt": "2026-08-12T13:56:24Z",
        "checkedAt": "2026-08-13T11:15:00Z",
        "expiresAt": "2026-08-13T14:00:00Z",
        "nextRefreshAttemptAt": "2026-08-13T11:30:00Z",
        "state": "current",
        "isCached": False,
        "refreshFailed": False,
        "refreshDeferred": False,
    }
    assert result["warnings"]
    assert cache_path.is_file()
    assert len(calls) == 1

    cached = service.convert(conversion_arguments(value="20"))
    assert cached["approx"] == "120"
    assert cached["rate"]["isCached"] is True
    assert len(calls) == 1

    zero = service.convert(conversion_arguments(value="0"))
    assert zero["approx"] == "0"


def test_expired_cache_remains_usable_when_refresh_fails(tmp_path: Path) -> None:
    cache_path = tmp_path / "rates.json"
    ECBRateService(
        cache_path=cache_path,
        opener=response_opener(),
        clock=lambda: NOW,
    ).convert(conversion_arguments())

    expired = ECBRateService(
        cache_path=cache_path,
        opener=failing_opener,
        clock=lambda: NOW + timedelta(hours=25),
    ).convert(conversion_arguments())

    assert expired["approx"] == "60"
    assert expired["rate"]["state"] == "expired"
    assert expired["rate"]["isCached"] is True
    assert expired["rate"]["refreshFailed"] is True
    assert any("cached" in warning for warning in expired["warnings"])


def test_failed_forced_refresh_keeps_a_current_cache(tmp_path: Path) -> None:
    cache_path = tmp_path / "rates.json"
    ECBRateService(
        cache_path=cache_path,
        opener=response_opener(),
        clock=lambda: NOW,
    ).convert(conversion_arguments())

    cached = ECBRateService(
        cache_path=cache_path,
        opener=failing_opener,
        clock=lambda: NOW + timedelta(hours=1),
    ).convert(conversion_arguments(forceRefresh=True))

    assert cached["rate"]["state"] == "current"
    assert cached["rate"]["refreshFailed"] is True


def test_cache_expires_when_the_next_business_day_release_is_expected(tmp_path: Path) -> None:
    cache_path = tmp_path / "rates.json"
    ECBRateService(
        cache_path=cache_path,
        opener=response_opener(),
        clock=lambda: NOW,
    ).convert(conversion_arguments())

    after_expected_release = ECBRateService(
        cache_path=cache_path,
        opener=failing_opener,
        clock=lambda: NOW + timedelta(hours=3),
    ).convert(conversion_arguments())

    assert after_expected_release["rate"]["state"] == "expired"
    assert after_expected_release["rate"]["refreshFailed"] is True


def test_stale_feed_is_throttled_instead_of_refetched_for_every_conversion(tmp_path: Path) -> None:
    calls: list[str] = []
    current = [NOW + timedelta(hours=3)]
    service = ECBRateService(
        cache_path=tmp_path / "rates.json",
        opener=response_opener(calls=calls),
        clock=lambda: current[0],
    )

    first = service.convert(conversion_arguments())
    second = service.convert(conversion_arguments(value="20"))

    assert first["rate"]["state"] == "expired"
    assert first["rate"]["refreshDeferred"] is False
    assert second["rate"]["state"] == "expired"
    assert second["rate"]["refreshDeferred"] is True
    assert second["rate"]["isCached"] is True
    assert len(calls) == 1

    current[0] += timedelta(minutes=16)
    service.convert(conversion_arguments(value="30"))
    assert len(calls) == 2


def test_concurrent_currency_conversions_share_one_refresh(tmp_path: Path) -> None:
    calls: list[str] = []
    entered = threading.Event()
    release = threading.Event()

    def blocking_opener(request, *, timeout):
        calls.append(request.full_url)
        assert timeout == 4.0
        entered.set()
        assert release.wait(timeout=2)
        return FakeResponse(xml_rates(), last_modified="Wed, 12 Aug 2026 13:56:24 GMT")

    service = ECBRateService(
        cache_path=tmp_path / "rates.json",
        opener=blocking_opener,
        clock=lambda: NOW,
    )
    results: list[dict] = []
    first = threading.Thread(target=lambda: results.append(service.convert(conversion_arguments())))
    second = threading.Thread(target=lambda: results.append(service.convert(conversion_arguments(value="20"))))
    first.start()
    assert entered.wait(timeout=2)
    second.start()
    release.set()
    first.join(timeout=2)
    second.join(timeout=2)

    assert not first.is_alive()
    assert not second.is_alive()
    assert len(results) == 2
    assert len(calls) == 1


def test_concurrent_request_waits_until_the_refreshed_cache_is_published(
    tmp_path: Path,
) -> None:
    """A refresh throttle must never become visible before its cache snapshot."""
    cache_path = tmp_path / "rates.json"
    service = ECBRateService(
        cache_path=cache_path,
        opener=response_opener(),
        clock=lambda: NOW,
    )
    save_entered = threading.Event()
    release_save = threading.Event()
    second_loaded_cache = threading.Event()
    second_finished = threading.Event()
    results: list[dict] = []
    errors: list[BaseException] = []
    original_save = service._save_cache
    original_load = service._load_cache

    def blocking_save(snapshot) -> None:
        save_entered.set()
        assert release_save.wait(timeout=2)
        original_save(snapshot)

    def observed_load():
        cached = original_load()
        if threading.current_thread().name == "second-currency-request":
            second_loaded_cache.set()
        return cached

    service._save_cache = blocking_save
    service._load_cache = observed_load

    def convert(value: str) -> None:
        try:
            results.append(service.convert(conversion_arguments(value=value)))
        except BaseException as error:
            errors.append(error)
        finally:
            if threading.current_thread().name == "second-currency-request":
                second_finished.set()

    first = threading.Thread(target=convert, args=("10",), name="first-currency-request")
    second = threading.Thread(target=convert, args=("20",), name="second-currency-request")
    first.start()
    assert save_entered.wait(timeout=2)
    second.start()
    assert second_loaded_cache.wait(timeout=2)

    assert not second_finished.wait(timeout=0.1)
    release_save.set()
    first.join(timeout=2)
    second.join(timeout=2)

    assert not first.is_alive()
    assert not second.is_alive()
    assert errors == []
    assert sorted(result["approx"] for result in results) == ["120", "60"]


def test_no_cache_and_network_failure_is_sanitized(tmp_path: Path) -> None:
    service = ECBRateService(
        cache_path=tmp_path / "missing.json",
        opener=failing_opener,
        clock=lambda: NOW,
    )

    with pytest.raises(CalculatorError) as raised:
        service.convert(conversion_arguments())

    assert raised.value.code == "E_PROVIDER"
    assert str(raised.value) == "Currency rates are unavailable. Try again."
    assert "offline" not in str(raised.value)


def test_invalid_cache_does_not_become_a_successful_rate(tmp_path: Path) -> None:
    cache_path = tmp_path / "invalid.json"
    cache_path.write_text('{"version":1,"provider":"ECB","rates":{"EUR":"1"}}')
    service = ECBRateService(
        cache_path=cache_path,
        opener=failing_opener,
        clock=lambda: NOW,
    )

    with pytest.raises(CalculatorError) as raised:
        service.convert(conversion_arguments())

    assert raised.value.code == "E_PROVIDER"


def test_incomplete_feed_and_unsupported_currency_fail_closed(tmp_path: Path) -> None:
    incomplete = ECBRateService(
        cache_path=tmp_path / "incomplete.json",
        opener=response_opener(xml_rates({"USD": "1.2"})),
        clock=lambda: NOW,
    )
    with pytest.raises(CalculatorError) as raised:
        incomplete.convert(conversion_arguments())
    assert raised.value.code == "E_PROVIDER"

    complete = ECBRateService(
        cache_path=tmp_path / "complete.json",
        opener=response_opener(),
        clock=lambda: NOW,
    )
    with pytest.raises(CalculatorError) as raised:
        complete.convert(conversion_arguments(toCurrency="RUB"))
    assert raised.value.code == "E_CURRENCY"


def test_currency_input_contract_rejects_non_decimal_and_bad_refresh_flag(tmp_path: Path) -> None:
    service = ECBRateService(
        cache_path=tmp_path / "rates.json",
        opener=response_opener(),
        clock=lambda: NOW,
    )

    with pytest.raises(CalculatorError) as raised:
        service.convert(conversion_arguments(value="NaN"))
    assert raised.value.code == "E_INPUT"

    with pytest.raises(CalculatorError) as raised:
        service.convert(conversion_arguments(forceRefresh="yes"))
    assert raised.value.code == "E_INPUT"
