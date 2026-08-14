import Foundation

struct HistoryStore {
    private let defaults: UserDefaults
    private let key = "calculationHistory.v1"

    init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
    }

    func load() -> [HistoryEntry] {
        guard let data = defaults.data(forKey: key) else { return [] }
        guard let entries = try? JSONDecoder().decode([HistoryEntry].self, from: data) else {
            return []
        }
        let migrated = entries.map(migratingLegacyExpression)
        if migrated != entries {
            save(migrated)
        }
        return migrated
    }

    func save(_ entries: [HistoryEntry]) {
        guard let data = try? JSONEncoder().encode(Array(entries.prefix(100))) else { return }
        defaults.set(data, forKey: key)
    }

    private func migratingLegacyExpression(_ entry: HistoryEntry) -> HistoryEntry {
        let original = entry.expression
        let visible = readableLegacyExpression(original)
        guard visible != original else { return entry }
        return HistoryEntry(
            id: entry.id,
            expression: visible,
            executionExpression: entry.executionExpression ?? original,
            exact: entry.exact,
            result: entry.result,
            createdAt: entry.createdAt
        )
    }

    private func readableLegacyExpression(_ expression: String) -> String {
        let migrations = [
            (
                pattern: #"^(.+)([+-])\(\(\1\)\*\((.+)\)/100\)$"#,
                replacement: "$1$2$3%"
            ),
            (pattern: #"^(.+)\+-\((.+)\)$"#, replacement: "$1-$2"),
            (pattern: #"^\(\(0\)\+\((.+)\)\)$"#, replacement: "$1"),
        ]
        for migration in migrations where expression.range(
            of: migration.pattern,
            options: .regularExpression
        ) != nil {
            return expression.replacingOccurrences(
                of: migration.pattern,
                with: migration.replacement,
                options: .regularExpression
            )
        }
        return expression
    }
}
