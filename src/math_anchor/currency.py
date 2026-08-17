from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation, localcontext
from email.utils import parsedate_to_datetime
import json
import os
from pathlib import Path
import threading
import time as monotonic_time
from typing import Any, Callable
from urllib.request import Request, urlopen
from uuid import uuid4
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

from .errors import CalculatorError, require
from .validation import integer_arg, string_arg


ECB_DAILY_RATES_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
ECB_SOURCE_URL = (
    "https://www.ecb.europa.eu/stats/policy_and_exchange_rates/"
    "euro_reference_exchange_rates/html/index.en.html"
)
ECB_SOURCE_NAME = "European Central Bank"
ECB_SOURCE_SHORT_NAME = "ECB"
CACHE_MAX_AGE = timedelta(hours=24)
REFRESH_RETRY_INTERVAL = timedelta(minutes=15)
ECB_RELEASE_ZONE = ZoneInfo("Europe/Berlin")
ECB_EXPECTED_RELEASE_TIME = time(hour=16)
MAX_RESPONSE_BYTES = 512 * 1024
MAX_CACHE_BYTES = 512 * 1024
MINIMUM_RATE_COUNT = 20


@dataclass(frozen=True)
class RateSnapshot:
    rate_date: str
    published_at: datetime | None
    checked_at: datetime
    expires_at: datetime
    next_refresh_attempt_at: datetime
    rates: dict[str, Decimal]


class ECBRateService:
    def __init__(
        self,
        *,
        cache_path: Path | None = None,
        opener: Callable[..., Any] = urlopen,
        clock: Callable[[], datetime] | None = None,
        timeout: float = 4.0,
    ) -> None:
        self.cache_path = cache_path or _default_cache_path()
        self.opener = opener
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.timeout = timeout
        self._refresh_condition = threading.Condition()
        self._refreshing = False
        self._next_refresh_attempt_at: datetime | None = None

    def convert(self, arguments: dict[str, Any]) -> dict[str, Any]:
        value = string_arg(arguments, "value", max_length=128)
        from_currency = _currency_code(arguments, "fromCurrency")
        to_currency = _currency_code(arguments, "toCurrency")
        precision = integer_arg(arguments, "precision", default=12, minimum=2, maximum=16)
        force_refresh = arguments.get("forceRefresh", False)
        require(isinstance(force_refresh, bool), "E_INPUT", "forceRefresh must be a boolean")
        amount = _decimal_value(value)

        now = _as_utc(self.clock())
        snapshot, fetched, refresh_failed, refresh_deferred = self._snapshot_for_conversion(
            now,
            force_refresh=force_refresh,
        )

        require(
            from_currency in snapshot.rates,
            "E_CURRENCY",
            f"currency is not available from ECB: {from_currency}",
        )
        require(
            to_currency in snapshot.rates,
            "E_CURRENCY",
            f"currency is not available from ECB: {to_currency}",
        )

        with localcontext() as context:
            context.prec = max(precision + 12, 32)
            result = amount / snapshot.rates[from_currency] * snapshot.rates[to_currency]
        approximate = _decimal_text(result, precision)
        expired = now >= snapshot.expires_at
        warnings = [
            "ECB reference rates are for information only and are not transaction quotes."
        ]
        if refresh_failed:
            warnings.append(
                "The latest refresh failed; a cached rate is being used."
            )
        elif refresh_deferred:
            warnings.append(
                "The rate is expired; the next automatic refresh attempt is deferred to avoid repeated provider requests."
            )

        return {
            "status": "ok",
            "operation": "currency.convert",
            "kind": "currency",
            "exact": None,
            "approx": approximate,
            "precision": precision,
            "unit": to_currency,
            "from": {"value": value, "currency": from_currency},
            "rate": {
                "sourceName": ECB_SOURCE_NAME,
                "sourceShortName": ECB_SOURCE_SHORT_NAME,
                "sourceURL": ECB_SOURCE_URL,
                "rateDate": snapshot.rate_date,
                "publishedAt": _iso_text(snapshot.published_at),
                "checkedAt": _iso_text(snapshot.checked_at),
                "expiresAt": _iso_text(snapshot.expires_at),
                "nextRefreshAttemptAt": _iso_text(snapshot.next_refresh_attempt_at),
                "state": "expired" if expired else "current",
                "isCached": not fetched,
                "refreshFailed": refresh_failed,
                "refreshDeferred": refresh_deferred,
            },
            "warnings": warnings,
        }

    def _snapshot_for_conversion(
        self,
        now: datetime,
        *,
        force_refresh: bool,
    ) -> tuple[RateSnapshot, bool, bool, bool]:
        coalesced = False
        wait_deadline = monotonic_time.monotonic() + self.timeout
        while True:
            cached = self._load_cache()
            with self._refresh_condition:
                if cached is not None:
                    self._next_refresh_attempt_at = max(
                        cached.next_refresh_attempt_at,
                        self._next_refresh_attempt_at or cached.next_refresh_attempt_at,
                    )
                if cached is not None and coalesced:
                    return cached, False, False, now < cached.next_refresh_attempt_at
                if cached is not None and not force_refresh and now < cached.expires_at:
                    return cached, False, False, False
                if self._refreshing:
                    remaining = wait_deadline - monotonic_time.monotonic()
                    if remaining <= 0:
                        if cached is not None:
                            return cached, False, True, True
                        raise CalculatorError(
                            "E_PROVIDER",
                            "Currency rates are unavailable. Try again.",
                        )
                    self._refresh_condition.wait(timeout=remaining)
                    coalesced = True
                    continue
                next_attempt = (
                    cached.next_refresh_attempt_at
                    if cached is not None
                    else self._next_refresh_attempt_at
                )
                if not force_refresh and next_attempt is not None and now < next_attempt:
                    if cached is None:
                        raise CalculatorError(
                            "E_PROVIDER",
                            "Currency rates are unavailable. Try again.",
                        )
                    return cached, False, False, True
                self._refreshing = True
                break

        published_next_attempt_at: datetime | None = None
        try:
            snapshot = self._fetch(now)
            self._save_cache(snapshot)
            published_next_attempt_at = snapshot.next_refresh_attempt_at
            return snapshot, True, False, False
        except Exception as error:
            next_attempt = now + REFRESH_RETRY_INTERVAL
            published_next_attempt_at = next_attempt
            if cached is None:
                raise CalculatorError(
                    "E_PROVIDER",
                    "Currency rates are unavailable. Try again.",
                ) from error
            snapshot = replace(cached, next_refresh_attempt_at=next_attempt)
            self._save_cache(snapshot)
            return snapshot, False, True, False
        finally:
            with self._refresh_condition:
                if published_next_attempt_at is not None:
                    self._next_refresh_attempt_at = published_next_attempt_at
                self._refreshing = False
                self._refresh_condition.notify_all()

    def _fetch(self, checked_at: datetime) -> RateSnapshot:
        request = Request(
            ECB_DAILY_RATES_URL,
            headers={
                "Accept": "application/xml,text/xml",
                "User-Agent": "Math Anchor/0.1 local macOS calculator",
            },
            method="GET",
        )
        with self.opener(request, timeout=self.timeout) as response:
            body = response.read(MAX_RESPONSE_BYTES + 1)
            require(
                len(body) <= MAX_RESPONSE_BYTES,
                "E_PROVIDER",
                "Currency rate response is too large.",
            )
            last_modified = response.headers.get("Last-Modified")

        rate_date, rates = _parse_ecb_rates(body)
        published_at = _http_datetime(last_modified)
        return RateSnapshot(
            rate_date=rate_date,
            published_at=published_at,
            checked_at=checked_at,
            expires_at=_fresh_until(rate_date, checked_at),
            next_refresh_attempt_at=checked_at + REFRESH_RETRY_INTERVAL,
            rates=rates,
        )

    def _load_cache(self) -> RateSnapshot | None:
        path = self.cache_path
        try:
            if path.is_symlink() or not path.is_file():
                return None
            if path.stat().st_size > MAX_CACHE_BYTES:
                return None
            payload = json.loads(path.read_text(encoding="utf-8"))
            return _snapshot_from_json(payload)
        except (
            CalculatorError,
            InvalidOperation,
            OSError,
            ValueError,
            TypeError,
            json.JSONDecodeError,
        ):
            return None

    def _save_cache(self, snapshot: RateSnapshot) -> None:
        path = self.cache_path
        temporary = path.with_name(f".{path.name}.{os.getpid()}.{uuid4().hex}.tmp")
        payload = {
            "version": 1,
            "provider": "ECB",
            "rateDate": snapshot.rate_date,
            "publishedAt": _iso_text(snapshot.published_at),
            "checkedAt": _iso_text(snapshot.checked_at),
            "expiresAt": _iso_text(snapshot.expires_at),
            "nextRefreshAttemptAt": _iso_text(snapshot.next_refresh_attempt_at),
            "rates": {currency: str(rate) for currency, rate in snapshot.rates.items()},
        }
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with temporary.open("x", encoding="utf-8") as handle:
                os.chmod(temporary, 0o600)
                json.dump(payload, handle, ensure_ascii=True, separators=(",", ":"))
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        except OSError:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


def currency_convert(
    arguments: dict[str, Any],
    *,
    service: ECBRateService | None = None,
) -> dict[str, Any]:
    return (service or ECBRateService()).convert(arguments)


def _default_cache_path() -> Path:
    override = os.environ.get("MATH_ANCHOR_CURRENCY_CACHE_PATH")
    if override:
        return Path(override).expanduser()
    return (
        Path.home()
        / "Library"
        / "Caches"
        / "com.openadam.mathanchor"
        / "ecb-rates-v1.json"
    )


def _currency_code(arguments: dict[str, Any], key: str) -> str:
    value = string_arg(arguments, key, max_length=3).upper()
    require(
        len(value) == 3 and value.isascii() and value.isalpha(),
        "E_INPUT",
        f"{key} must be a three-letter currency code",
    )
    return value


def _decimal_value(value: str) -> Decimal:
    try:
        parsed = Decimal(value)
    except InvalidOperation as error:
        raise CalculatorError("E_INPUT", "value must be decimal text") from error
    require(parsed.is_finite(), "E_INPUT", "value must be finite decimal text")
    return parsed


def _parse_ecb_rates(body: bytes) -> tuple[str, dict[str, Decimal]]:
    try:
        root = ET.fromstring(body)
    except ET.ParseError as error:
        raise CalculatorError("E_PROVIDER", "Currency rate response is invalid.") from error

    rate_date: str | None = None
    rates: dict[str, Decimal] = {"EUR": Decimal("1")}
    for element in root.iter():
        if "time" in element.attrib:
            rate_date = element.attrib["time"]
        currency = element.attrib.get("currency")
        rate = element.attrib.get("rate")
        if currency and rate:
            try:
                parsed_rate = Decimal(rate)
            except InvalidOperation as error:
                raise CalculatorError("E_PROVIDER", "Currency rate response is invalid.") from error
            require(
                parsed_rate.is_finite() and parsed_rate > 0,
                "E_PROVIDER",
                "Currency rate response contains an invalid rate.",
            )
            rates[currency.upper()] = parsed_rate

    require(rate_date is not None, "E_PROVIDER", "Currency rate date is missing.")
    _parse_rate_date(rate_date)
    require(
        len(rates) >= MINIMUM_RATE_COUNT,
        "E_PROVIDER",
        "Currency rate response is incomplete.",
    )
    return rate_date, rates


def _snapshot_from_json(payload: Any) -> RateSnapshot:
    require(isinstance(payload, dict), "E_PROVIDER", "Currency rate cache is invalid.")
    require(payload.get("version") == 1, "E_PROVIDER", "Currency rate cache is invalid.")
    require(payload.get("provider") == "ECB", "E_PROVIDER", "Currency rate cache is invalid.")
    rate_date = payload.get("rateDate")
    rates_payload = payload.get("rates")
    require(isinstance(rate_date, str), "E_PROVIDER", "Currency rate cache is invalid.")
    require(isinstance(rates_payload, dict), "E_PROVIDER", "Currency rate cache is invalid.")
    _parse_rate_date(rate_date)
    rates: dict[str, Decimal] = {}
    for currency, value in rates_payload.items():
        require(
            isinstance(currency, str) and len(currency) == 3 and isinstance(value, str),
            "E_PROVIDER",
            "Currency rate cache is invalid.",
        )
        parsed = Decimal(value)
        require(
            parsed.is_finite() and parsed > 0,
            "E_PROVIDER",
            "Currency rate cache is invalid.",
        )
        rates[currency] = parsed
    require(
        rates.get("EUR") == Decimal("1") and len(rates) >= MINIMUM_RATE_COUNT,
        "E_PROVIDER",
        "Currency rate cache is incomplete.",
    )
    checked_at = _parse_iso(payload.get("checkedAt"))
    stored_expires_at = _parse_iso(payload.get("expiresAt"))
    assert checked_at is not None and stored_expires_at is not None
    return RateSnapshot(
        rate_date=rate_date,
        published_at=_parse_iso(payload.get("publishedAt"), optional=True),
        checked_at=checked_at,
        # Older caches used checkedAt + 24 hours even when a newer business-day
        # publication was already expected. Recompute the conservative cutoff
        # while retaining any earlier stored expiry.
        expires_at=min(stored_expires_at, _fresh_until(rate_date, checked_at)),
        next_refresh_attempt_at=(
            _parse_iso(payload.get("nextRefreshAttemptAt"), optional=True)
            or checked_at
        ),
        rates=rates,
    )


def _parse_rate_date(value: str) -> None:
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError as error:
        raise CalculatorError("E_PROVIDER", "Currency rate date is invalid.") from error


def _fresh_until(rate_date: str, checked_at: datetime) -> datetime:
    parsed_rate_date = datetime.strptime(rate_date, "%Y-%m-%d").date()
    next_business_day = _next_business_day(parsed_rate_date)
    expected_release = datetime.combine(
        next_business_day,
        ECB_EXPECTED_RELEASE_TIME,
        tzinfo=ECB_RELEASE_ZONE,
    ).astimezone(timezone.utc)
    return min(_as_utc(checked_at) + CACHE_MAX_AGE, expected_release)


def _next_business_day(value: date) -> date:
    candidate = value + timedelta(days=1)
    while candidate.weekday() >= 5:
        candidate += timedelta(days=1)
    return candidate


def _parse_iso(value: Any, *, optional: bool = False) -> datetime | None:
    if optional and value is None:
        return None
    require(isinstance(value, str), "E_PROVIDER", "Currency rate timestamp is invalid.")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise CalculatorError("E_PROVIDER", "Currency rate timestamp is invalid.") from error
    require(parsed.tzinfo is not None, "E_PROVIDER", "Currency rate timestamp is invalid.")
    return _as_utc(parsed)


def _http_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        return _as_utc(parsedate_to_datetime(value))
    except (TypeError, ValueError, OverflowError):
        return None


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _iso_text(value: datetime | None) -> str | None:
    if value is None:
        return None
    return _as_utc(value).isoformat(timespec="seconds").replace("+00:00", "Z")


def _decimal_text(value: Decimal, precision: int) -> str:
    if value.is_zero():
        return "0"
    text = format(value, f".{precision}g").lower()
    if "e" not in text and "." in text:
        text = text.rstrip("0").rstrip(".")
    return "0" if text in {"-0", ""} else text
