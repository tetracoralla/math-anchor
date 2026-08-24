import Foundation

enum UnitCategory: String, CaseIterable, Identifiable, Sendable {
    case length
    case area
    case volume
    case mass
    case temperature
    case speed
    case time
    case pressure
    case energy
    case power
    case angle
    case data
    case dataRate = "data rate"
    case frequency
    case force
    case acceleration
    case torque
    case density
    case currency

    var id: Self { self }

    var title: String {
        rawValue.capitalized
    }
}

struct UnitDefinition: Identifiable, Hashable, Sendable {
    let id: String
    let name: String
    let symbol: String
    let category: UnitCategory
    let runtimeUnit: String

    var isCurrency: Bool {
        category == .currency
    }
}

enum HumanUnitCatalog {
    static let all: [UnitDefinition] = [
        unit("meter", "Meter", "m", .length),
        unit("kilometer", "Kilometer", "km", .length),
        unit("centimeter", "Centimeter", "cm", .length),
        unit("millimeter", "Millimeter", "mm", .length),
        unit("inch", "Inch", "in", .length),
        unit("foot", "Foot", "ft", .length),
        unit("yard", "Yard", "yd", .length),
        unit("mile", "Mile", "mi", .length),

        unit("square-meter", "Square meter", "m²", .area, runtimeUnit: "meter ** 2"),
        unit("square-kilometer", "Square kilometer", "km²", .area, runtimeUnit: "kilometer ** 2"),
        unit("square-foot", "Square foot", "ft²", .area, runtimeUnit: "foot ** 2"),
        unit("acre", "Acre", "ac", .area),
        unit("hectare", "Hectare", "ha", .area),

        unit("liter", "Liter", "L", .volume),
        unit("milliliter", "Milliliter", "mL", .volume),
        unit("cubic-meter", "Cubic meter", "m³", .volume, runtimeUnit: "meter ** 3"),
        unit("gallon", "US gallon", "gal", .volume),
        unit("imperial-gallon", "Imperial gallon", "imp gal", .volume, runtimeUnit: "imperial_gallon"),
        unit("fluid-ounce", "US fluid ounce", "fl oz", .volume, runtimeUnit: "fluid_ounce"),

        unit("kilogram", "Kilogram", "kg", .mass),
        unit("gram", "Gram", "g", .mass),
        unit("milligram", "Milligram", "mg", .mass),
        unit("metric-ton", "Metric ton", "t", .mass, runtimeUnit: "metric_ton"),
        unit("pound", "Pound", "lb", .mass),
        unit("ounce", "Ounce", "oz", .mass),

        unit("celsius", "Celsius", "°C", .temperature, runtimeUnit: "degC"),
        unit("fahrenheit", "Fahrenheit", "°F", .temperature, runtimeUnit: "degF"),
        unit("kelvin", "Kelvin", "K", .temperature),

        unit("meter-per-second", "Meters per second", "m/s", .speed, runtimeUnit: "meter / second"),
        unit("kilometer-per-hour", "Kilometers per hour", "km/h", .speed, runtimeUnit: "kilometer / hour"),
        unit("mile-per-hour", "Miles per hour", "mph", .speed, runtimeUnit: "mile / hour"),
        unit("knot", "Knot", "kn", .speed),

        unit("second", "Second", "s", .time),
        unit("minute", "Minute", "min", .time),
        unit("hour", "Hour", "h", .time),
        unit("day", "Day", "d", .time),
        unit("week", "Week", "wk", .time),

        unit("pascal", "Pascal", "Pa", .pressure),
        unit("kilopascal", "Kilopascal", "kPa", .pressure),
        unit("bar", "Bar", "bar", .pressure),
        unit("atmosphere", "Atmosphere", "atm", .pressure),
        unit("psi", "Pounds per square inch", "psi", .pressure),

        unit("joule", "Joule", "J", .energy),
        unit("kilojoule", "Kilojoule", "kJ", .energy),
        unit("watt-hour", "Watt-hour", "Wh", .energy, runtimeUnit: "watt_hour"),
        unit("kilowatt-hour", "Kilowatt-hour", "kWh", .energy, runtimeUnit: "kilowatt_hour"),
        unit("calorie", "Calorie", "cal", .energy),
        unit("kilocalorie", "Kilocalorie", "kcal", .energy),

        unit("watt", "Watt", "W", .power),
        unit("kilowatt", "Kilowatt", "kW", .power),
        unit("horsepower", "Horsepower", "hp", .power),

        unit("degree", "Degree", "°", .angle),
        unit("radian", "Radian", "rad", .angle),

        unit("bit", "Bit", "bit", .data),
        unit("byte", "Byte", "B", .data),
        unit("kilobit", "Kilobit", "kbit", .data),
        unit("kilobyte", "Kilobyte", "kB", .data),
        unit("megabit", "Megabit", "Mbit", .data),
        unit("megabyte", "Megabyte", "MB", .data),
        unit("gigabit", "Gigabit", "Gbit", .data),
        unit("gigabyte", "Gigabyte", "GB", .data),
        unit("kibibit", "Kibibit", "Kibit", .data),
        unit("kibibyte", "Kibibyte", "KiB", .data),
        unit("mebibit", "Mebibit", "Mibit", .data),
        unit("mebibyte", "Mebibyte", "MiB", .data),
        unit("gibibit", "Gibibit", "Gibit", .data),
        unit("gibibyte", "Gibibyte", "GiB", .data),

        unit("bit-per-second", "Bits per second", "bit/s", .dataRate, runtimeUnit: "bit / second"),
        unit("kilobit-per-second", "Kilobits per second", "kbit/s", .dataRate, runtimeUnit: "kilobit / second"),
        unit("megabit-per-second", "Megabits per second", "Mbit/s", .dataRate, runtimeUnit: "megabit / second"),
        unit("gigabit-per-second", "Gigabits per second", "Gbit/s", .dataRate, runtimeUnit: "gigabit / second"),
        unit("byte-per-second", "Bytes per second", "B/s", .dataRate, runtimeUnit: "byte / second"),
        unit("megabyte-per-second", "Megabytes per second", "MB/s", .dataRate, runtimeUnit: "megabyte / second"),
        unit("mebibyte-per-second", "Mebibytes per second", "MiB/s", .dataRate, runtimeUnit: "mebibyte / second"),

        unit("hertz", "Hertz", "Hz", .frequency),
        unit("kilohertz", "Kilohertz", "kHz", .frequency),
        unit("megahertz", "Megahertz", "MHz", .frequency),
        unit("gigahertz", "Gigahertz", "GHz", .frequency),

        unit("newton", "Newton", "N", .force),
        unit("kilonewton", "Kilonewton", "kN", .force),
        unit("pound-force", "Pound-force", "lbf", .force, runtimeUnit: "pound_force"),

        unit(
            "meter-per-second-squared",
            "Meters per second squared",
            "m/s²",
            .acceleration,
            runtimeUnit: "meter / second ** 2"
        ),
        unit(
            "foot-per-second-squared",
            "Feet per second squared",
            "ft/s²",
            .acceleration,
            runtimeUnit: "foot / second ** 2"
        ),
        unit(
            "standard-gravity",
            "Standard gravity",
            "g₀",
            .acceleration,
            runtimeUnit: "standard_gravity"
        ),

        unit("newton-meter", "Newton-meter", "N·m", .torque, runtimeUnit: "newton * meter"),
        unit(
            "pound-force-foot",
            "Pound-force foot",
            "lbf·ft",
            .torque,
            runtimeUnit: "pound_force * foot"
        ),

        unit(
            "kilogram-per-cubic-meter",
            "Kilograms per cubic meter",
            "kg/m³",
            .density,
            runtimeUnit: "kilogram / meter ** 3"
        ),
        unit(
            "gram-per-cubic-centimeter",
            "Grams per cubic centimeter",
            "g/cm³",
            .density,
            runtimeUnit: "gram / centimeter ** 3"
        ),
        unit(
            "pound-per-cubic-foot",
            "Pounds per cubic foot",
            "lb/ft³",
            .density,
            runtimeUnit: "pound / foot ** 3"
        ),

        unit("currency-eur", "Euro", "EUR", .currency, runtimeUnit: "EUR"),
        unit("currency-usd", "US dollar", "USD", .currency, runtimeUnit: "USD"),
        unit("currency-jpy", "Japanese yen", "JPY", .currency, runtimeUnit: "JPY"),
        unit("currency-czk", "Czech koruna", "CZK", .currency, runtimeUnit: "CZK"),
        unit("currency-dkk", "Danish krone", "DKK", .currency, runtimeUnit: "DKK"),
        unit("currency-gbp", "Pound sterling", "GBP", .currency, runtimeUnit: "GBP"),
        unit("currency-huf", "Hungarian forint", "HUF", .currency, runtimeUnit: "HUF"),
        unit("currency-pln", "Polish zloty", "PLN", .currency, runtimeUnit: "PLN"),
        unit("currency-ron", "Romanian leu", "RON", .currency, runtimeUnit: "RON"),
        unit("currency-sek", "Swedish krona", "SEK", .currency, runtimeUnit: "SEK"),
        unit("currency-chf", "Swiss franc", "CHF", .currency, runtimeUnit: "CHF"),
        unit("currency-isk", "Icelandic krona", "ISK", .currency, runtimeUnit: "ISK"),
        unit("currency-nok", "Norwegian krone", "NOK", .currency, runtimeUnit: "NOK"),
        unit("currency-try", "Turkish lira", "TRY", .currency, runtimeUnit: "TRY"),
        unit("currency-aud", "Australian dollar", "AUD", .currency, runtimeUnit: "AUD"),
        unit("currency-brl", "Brazilian real", "BRL", .currency, runtimeUnit: "BRL"),
        unit("currency-cad", "Canadian dollar", "CAD", .currency, runtimeUnit: "CAD"),
        unit("currency-cny", "Chinese yuan", "CNY", .currency, runtimeUnit: "CNY"),
        unit("currency-hkd", "Hong Kong dollar", "HKD", .currency, runtimeUnit: "HKD"),
        unit("currency-idr", "Indonesian rupiah", "IDR", .currency, runtimeUnit: "IDR"),
        unit("currency-ils", "Israeli new shekel", "ILS", .currency, runtimeUnit: "ILS"),
        unit("currency-inr", "Indian rupee", "INR", .currency, runtimeUnit: "INR"),
        unit("currency-krw", "South Korean won", "KRW", .currency, runtimeUnit: "KRW"),
        unit("currency-mxn", "Mexican peso", "MXN", .currency, runtimeUnit: "MXN"),
        unit("currency-myr", "Malaysian ringgit", "MYR", .currency, runtimeUnit: "MYR"),
        unit("currency-nzd", "New Zealand dollar", "NZD", .currency, runtimeUnit: "NZD"),
        unit("currency-php", "Philippine peso", "PHP", .currency, runtimeUnit: "PHP"),
        unit("currency-sgd", "Singapore dollar", "SGD", .currency, runtimeUnit: "SGD"),
        unit("currency-thb", "Thai baht", "THB", .currency, runtimeUnit: "THB"),
        unit("currency-zar", "South African rand", "ZAR", .currency, runtimeUnit: "ZAR"),
    ]

    static let meter = all.first { $0.id == "meter" }!
    static let foot = all.first { $0.id == "foot" }!
    static let euro = all.first { $0.id == "currency-eur" }!
    static let usDollar = all.first { $0.id == "currency-usd" }!

    static func units(in category: UnitCategory) -> [UnitDefinition] {
        all.filter { $0.category == category }
    }

    static func alternate(to unit: UnitDefinition) -> UnitDefinition {
        units(in: unit.category).first { $0.id != unit.id } ?? unit
    }

    private static func unit(
        _ id: String,
        _ name: String,
        _ symbol: String,
        _ category: UnitCategory,
        runtimeUnit: String? = nil
    ) -> UnitDefinition {
        UnitDefinition(
            id: id,
            name: name,
            symbol: symbol,
            category: category,
            runtimeUnit: runtimeUnit ?? id
        )
    }
}
