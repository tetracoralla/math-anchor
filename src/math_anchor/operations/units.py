from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from ..errors import CalculatorError, require
from ..validation import integer_arg


@dataclass(frozen=True)
class UnitDefinition:
    id: str
    category: str
    name: str
    symbol: str
    runtime_unit: str
    aliases: tuple[str, ...] = ()


def _unit(
    id: str,
    category: str,
    name: str,
    symbol: str,
    *,
    runtime_unit: str | None = None,
    aliases: tuple[str, ...] = (),
) -> UnitDefinition:
    return UnitDefinition(id, category, name, symbol, runtime_unit or id, aliases)


# This is the small, stable Agent-facing catalog. Pint still supplies the much
# larger conversion engine; these IDs are the spellings Math Anchor promises
# not to make callers guess or inherit from a particular Pint release.
UNIT_CATALOG: tuple[UnitDefinition, ...] = (
    _unit("meter", "length", "Meter", "m", aliases=("metre", "米", "公尺")),
    _unit("kilometer", "length", "Kilometer", "km", aliases=("kilometre", "公里", "千米")),
    _unit("centimeter", "length", "Centimeter", "cm", aliases=("centimetre", "厘米")),
    _unit("millimeter", "length", "Millimeter", "mm", aliases=("millimetre", "毫米")),
    _unit("inch", "length", "Inch", "in", aliases=("英寸",)),
    _unit("foot", "length", "Foot", "ft", aliases=("feet", "英尺")),
    _unit("yard", "length", "Yard", "yd", aliases=("码",)),
    _unit("mile", "length", "Mile", "mi", aliases=("英里",)),
    _unit("square-meter", "area", "Square meter", "m²", runtime_unit="meter ** 2", aliases=("平方米",)),
    _unit("square-kilometer", "area", "Square kilometer", "km²", runtime_unit="kilometer ** 2", aliases=("平方公里", "平方千米")),
    _unit("square-foot", "area", "Square foot", "ft²", runtime_unit="foot ** 2", aliases=("平方英尺",)),
    _unit("acre", "area", "Acre", "ac", aliases=("英亩",)),
    _unit("hectare", "area", "Hectare", "ha", aliases=("公顷",)),
    _unit("liter", "volume", "Liter", "L", aliases=("litre", "升", "公升")),
    _unit("milliliter", "volume", "Milliliter", "mL", aliases=("millilitre", "毫升")),
    _unit("cubic-meter", "volume", "Cubic meter", "m³", runtime_unit="meter ** 3", aliases=("立方米",)),
    _unit("gallon", "volume", "US gallon", "gal", aliases=("美制加仑",)),
    _unit("imperial-gallon", "volume", "Imperial gallon", "imp gal", runtime_unit="imperial_gallon", aliases=("英制加仑",)),
    _unit("fluid-ounce", "volume", "US fluid ounce", "fl oz", runtime_unit="fluid_ounce", aliases=("液量盎司",)),
    _unit("kilogram", "mass", "Kilogram", "kg", aliases=("千克", "公斤")),
    _unit("gram", "mass", "Gram", "g", aliases=("克",)),
    _unit("milligram", "mass", "Milligram", "mg", aliases=("毫克",)),
    _unit("metric-ton", "mass", "Metric ton", "t", runtime_unit="metric_ton", aliases=("tonne", "公吨", "吨")),
    _unit("pound", "mass", "Pound", "lb", aliases=("磅",)),
    _unit("ounce", "mass", "Ounce", "oz", aliases=("盎司",)),
    _unit("celsius", "temperature", "Celsius", "°C", runtime_unit="degC", aliases=("摄氏", "摄氏度")),
    _unit("fahrenheit", "temperature", "Fahrenheit", "°F", runtime_unit="degF", aliases=("华氏", "华氏度")),
    _unit("kelvin", "temperature", "Kelvin", "K", aliases=("开尔文",)),
    _unit("meter-per-second", "speed", "Meters per second", "m/s", runtime_unit="meter / second", aliases=("米每秒",)),
    _unit("kilometer-per-hour", "speed", "Kilometers per hour", "km/h", runtime_unit="kilometer / hour", aliases=("公里每小时", "千米每小时")),
    _unit("mile-per-hour", "speed", "Miles per hour", "mph", runtime_unit="mile / hour", aliases=("英里每小时",)),
    _unit("knot", "speed", "Knot", "kn", aliases=("节",)),
    _unit("second", "time", "Second", "s", aliases=("秒",)),
    _unit("minute", "time", "Minute", "min", aliases=("分钟", "分")),
    _unit("hour", "time", "Hour", "h", aliases=("小时", "时")),
    _unit("day", "time", "Day", "d", aliases=("天", "日")),
    _unit("week", "time", "Week", "wk", aliases=("周", "星期")),
    _unit("pascal", "pressure", "Pascal", "Pa", aliases=("帕", "帕斯卡")),
    _unit("kilopascal", "pressure", "Kilopascal", "kPa", aliases=("千帕",)),
    _unit("bar", "pressure", "Bar", "bar", aliases=("巴",)),
    _unit("atmosphere", "pressure", "Standard atmosphere", "atm", aliases=("标准大气压", "大气压")),
    _unit("psi", "pressure", "Pounds per square inch", "psi", aliases=("磅每平方英寸",)),
    _unit("joule", "energy", "Joule", "J", aliases=("焦耳",)),
    _unit("kilojoule", "energy", "Kilojoule", "kJ", aliases=("千焦", "千焦耳")),
    _unit("watt-hour", "energy", "Watt-hour", "Wh", runtime_unit="watt_hour", aliases=("瓦时",)),
    _unit("kilowatt-hour", "energy", "Kilowatt-hour", "kWh", runtime_unit="kilowatt_hour", aliases=("千瓦时", "度电")),
    _unit("calorie", "energy", "Calorie", "cal", aliases=("卡路里", "卡")),
    _unit("kilocalorie", "energy", "Kilocalorie", "kcal", aliases=("千卡", "大卡")),
    _unit("watt", "power", "Watt", "W", aliases=("瓦", "瓦特")),
    _unit("kilowatt", "power", "Kilowatt", "kW", aliases=("千瓦",)),
    _unit("horsepower", "power", "Horsepower", "hp", aliases=("马力",)),
    _unit("degree", "angle", "Degree", "°", aliases=("角度", "度")),
    _unit("radian", "angle", "Radian", "rad", aliases=("弧度",)),
    _unit("bit", "data", "Bit", "bit", aliases=("比特", "位")),
    _unit("byte", "data", "Byte", "B", aliases=("字节",)),
    _unit("kilobit", "data", "Kilobit", "kbit", aliases=("千比特",)),
    _unit("kilobyte", "data", "Kilobyte", "kB", aliases=("千字节",)),
    _unit("megabit", "data", "Megabit", "Mbit", aliases=("兆比特",)),
    _unit("megabyte", "data", "Megabyte", "MB", aliases=("兆字节",)),
    _unit("gigabit", "data", "Gigabit", "Gbit", aliases=("吉比特",)),
    _unit("gigabyte", "data", "Gigabyte", "GB", aliases=("吉字节",)),
    _unit("kibibit", "data", "Kibibit", "Kibit", aliases=("binary kilobit",)),
    _unit("kibibyte", "data", "Kibibyte", "KiB", aliases=("binary kilobyte",)),
    _unit("mebibit", "data", "Mebibit", "Mibit", aliases=("binary megabit",)),
    _unit("mebibyte", "data", "Mebibyte", "MiB", aliases=("binary megabyte",)),
    _unit("gibibit", "data", "Gibibit", "Gibit", aliases=("binary gigabit",)),
    _unit("gibibyte", "data", "Gibibyte", "GiB", aliases=("binary gigabyte",)),
    _unit("bit-per-second", "data_rate", "Bits per second", "bit/s", runtime_unit="bit / second", aliases=("bps", "比特每秒")),
    _unit("kilobit-per-second", "data_rate", "Kilobits per second", "kbit/s", runtime_unit="kilobit / second", aliases=("kbps", "千比特每秒")),
    _unit("megabit-per-second", "data_rate", "Megabits per second", "Mbit/s", runtime_unit="megabit / second", aliases=("mbps", "兆比特每秒")),
    _unit("gigabit-per-second", "data_rate", "Gigabits per second", "Gbit/s", runtime_unit="gigabit / second", aliases=("gbps", "吉比特每秒")),
    _unit("byte-per-second", "data_rate", "Bytes per second", "B/s", runtime_unit="byte / second", aliases=("字节每秒",)),
    _unit("megabyte-per-second", "data_rate", "Megabytes per second", "MB/s", runtime_unit="megabyte / second", aliases=("兆字节每秒",)),
    _unit("mebibyte-per-second", "data_rate", "Mebibytes per second", "MiB/s", runtime_unit="mebibyte / second", aliases=("binary megabytes per second",)),
    _unit("hertz", "frequency", "Hertz", "Hz", aliases=("赫兹",)),
    _unit("kilohertz", "frequency", "Kilohertz", "kHz", aliases=("千赫", "千赫兹")),
    _unit("megahertz", "frequency", "Megahertz", "MHz", aliases=("兆赫", "兆赫兹")),
    _unit("gigahertz", "frequency", "Gigahertz", "GHz", aliases=("吉赫", "吉赫兹")),
    _unit("newton", "force", "Newton", "N", aliases=("牛顿", "牛")),
    _unit("kilonewton", "force", "Kilonewton", "kN", aliases=("千牛", "千牛顿")),
    _unit("pound-force", "force", "Pound-force", "lbf", runtime_unit="pound_force", aliases=("磅力",)),
    _unit("meter-per-second-squared", "acceleration", "Meters per second squared", "m/s²", runtime_unit="meter / second ** 2", aliases=("米每二次方秒", "米每秒平方")),
    _unit("foot-per-second-squared", "acceleration", "Feet per second squared", "ft/s²", runtime_unit="foot / second ** 2", aliases=("英尺每秒平方",)),
    _unit("standard-gravity", "acceleration", "Standard gravity", "g₀", runtime_unit="standard_gravity", aliases=("gravity", "重力加速度", "标准重力")),
    _unit("newton-meter", "torque", "Newton-meter", "N·m", runtime_unit="newton * meter", aliases=("牛顿米", "牛米", "扭矩")),
    _unit("pound-force-foot", "torque", "Pound-force foot", "lbf·ft", runtime_unit="pound_force * foot", aliases=("磅力英尺",)),
    _unit("kilogram-per-cubic-meter", "density", "Kilograms per cubic meter", "kg/m³", runtime_unit="kilogram / meter ** 3", aliases=("千克每立方米", "公斤每立方米")),
    _unit("gram-per-cubic-centimeter", "density", "Grams per cubic centimeter", "g/cm³", runtime_unit="gram / centimeter ** 3", aliases=("克每立方厘米",)),
    _unit("pound-per-cubic-foot", "density", "Pounds per cubic foot", "lb/ft³", runtime_unit="pound / foot ** 3", aliases=("磅每立方英尺",)),
)


UNIT_CATEGORIES: tuple[str, ...] = tuple(dict.fromkeys(unit.category for unit in UNIT_CATALOG))
_UNITS_BY_ID = {unit.id: unit for unit in UNIT_CATALOG}
_SEARCH_WORD = re.compile(r"[a-z0-9]+")
_CALENDAR_UNITS = frozenset({"month", "year"})
CALENDAR_POLICIES = ("reject", "average_duration")
CALENDAR_AVERAGE_WARNING = (
    "Calendar months and years are civil-calendar concepts. This result uses "
    "fixed average-duration definitions and is not date or time-zone arithmetic."
)


def resolve_unit_text(value: str) -> str:
    definition = _UNITS_BY_ID.get(value)
    return definition.runtime_unit if definition is not None else value


def calendar_unit_names(parsed_unit: Any) -> set[str]:
    try:
        components = set(parsed_unit._units)
    except AttributeError as error:
        # Pint's internal unit-component layout moved; verification is no
        # longer possible, and silently treating every unit as non-calendar
        # would let month/year convert through fixed average durations
        # without the required explicit policy. Fail closed instead.
        raise CalculatorError(
            "E_UNIT",
            "calendar policy cannot be verified for this unit expression",
        ) from error
    return components.intersection(_CALENDAR_UNITS)


def require_calendar_policy(names: set[str], policy: str) -> bool:
    if not names:
        return False
    if policy == "reject":
        readable = ", ".join(sorted(names))
        raise CalculatorError(
            "E_UNIT",
            f"calendar unit {readable} requires calendarPolicy='average_duration'; "
            "use date/time-zone arithmetic for civil calendar calculations",
        )
    return True


def search(arguments: dict[str, Any]) -> dict[str, Any]:
    raw_query = arguments.get("query", "")
    query = raw_query.strip() if isinstance(raw_query, str) else ""
    category = arguments.get("category")
    if category is not None:
        # The generated JSON-Schema enum is the live ingress guard; this
        # keeps direct registry callers equally fail-closed.
        require(
            isinstance(category, str) and category in UNIT_CATEGORIES,
            "E_INPUT",
            "category must be null or a known unit category",
        )
    limit = integer_arg(arguments, "limit", default=20, minimum=1, maximum=50)
    normalized = query.casefold()
    query_words = set(_SEARCH_WORD.findall(normalized))

    ranked: list[tuple[int, int, UnitDefinition]] = []
    for index, unit in enumerate(UNIT_CATALOG):
        if category is not None and unit.category != category:
            continue
        fields = (unit.id, unit.name, unit.symbol, unit.category, *unit.aliases)
        normalized_fields = tuple(field.casefold() for field in fields)
        if not normalized:
            score = 0
        elif normalized in normalized_fields:
            score = 100
        elif any(field.startswith(normalized) for field in normalized_fields):
            score = 80
        elif any(normalized in field for field in normalized_fields):
            score = 60
        elif query_words and query_words.issubset(
            set().union(*(_SEARCH_WORD.findall(field) for field in normalized_fields))
        ):
            score = 40
        else:
            continue
        ranked.append((-score, index, unit))

    ranked.sort(key=lambda item: (item[0], item[1]))
    matching = [item[2] for item in ranked]
    return {
        "status": "ok",
        "operation": "units.search",
        "kind": "unit_catalog",
        "query": query,
        "category": category,
        "count": len(matching),
        "units": [
            {
                "id": unit.id,
                "category": unit.category,
                "name": unit.name,
                "symbol": unit.symbol,
                "runtimeUnit": unit.runtime_unit,
            }
            for unit in matching[:limit]
        ],
        "warnings": [],
    }
