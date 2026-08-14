import Foundation
import Darwin

final class MathRuntimeService: MathEvaluating, UnitConverting, CurrencyConverting, @unchecked Sendable {
    private struct RuntimeRequest: Encodable {
        let id: String
        let operation: String
        let expression: String?
        let value: String?
        let fromUnit: String?
        let toUnit: String?
        let fromCurrency: String?
        let toCurrency: String?
        let forceRefresh: Bool?
        let precision: Int
    }

    private enum RuntimeOperation: Sendable {
        case evaluate(expression: String, precision: Int)
        case convert(value: String, fromUnit: String, toUnit: String, precision: Int)
        case convertCurrency(
            value: String,
            fromCurrency: String,
            toCurrency: String,
            precision: Int,
            forceRefresh: Bool
        )

        func request(id: String) -> RuntimeRequest {
            switch self {
            case let .evaluate(expression, precision):
                RuntimeRequest(
                    id: id,
                    operation: "expression.evaluate",
                    expression: expression,
                    value: nil,
                    fromUnit: nil,
                    toUnit: nil,
                    fromCurrency: nil,
                    toCurrency: nil,
                    forceRefresh: nil,
                    precision: precision
                )
            case let .convert(value, fromUnit, toUnit, precision):
                RuntimeRequest(
                    id: id,
                    operation: "units.convert",
                    expression: nil,
                    value: value,
                    fromUnit: fromUnit,
                    toUnit: toUnit,
                    fromCurrency: nil,
                    toCurrency: nil,
                    forceRefresh: nil,
                    precision: precision
                )
            case let .convertCurrency(
                value,
                fromCurrency,
                toCurrency,
                precision,
                forceRefresh
            ):
                RuntimeRequest(
                    id: id,
                    operation: "currency.convert",
                    expression: nil,
                    value: value,
                    fromUnit: nil,
                    toUnit: nil,
                    fromCurrency: fromCurrency,
                    toCurrency: toCurrency,
                    forceRefresh: forceRefresh,
                    precision: precision
                )
            }
        }
    }

    private struct RuntimeErrorPayload: Decodable {
        let message: String
    }

    private struct RuntimePayload: Decodable {
        let id: String?
        let status: String
        let exact: String?
        let approx: String?
        let unit: String?
        let rate: RuntimeRatePayload?
        let warnings: [String]?
        let error: RuntimeErrorPayload?
    }

    private struct RuntimeRatePayload: Decodable {
        let sourceName: String
        let sourceShortName: String
        let sourceURL: String
        let rateDate: String
        let publishedAt: String?
        let checkedAt: String
        let expiresAt: String
        let nextRefreshAttemptAt: String?
        let state: String
        let isCached: Bool
        let refreshFailed: Bool
        let refreshDeferred: Bool?
    }

    private struct RuntimeLaunch {
        let executable: URL
        let arguments: [String]
        let workingDirectory: URL
    }

    private let queue = DispatchQueue(label: "com.openadam.zibetha.runtime", qos: .userInitiated)
    private var process: Process?
    private var inputHandle: FileHandle?
    private var outputHandle: FileHandle?
    private var responseBuffer = Data()
    private let cancellationLock = NSLock()
    private var cancellationRevision = 0
    private let requestTimeout: TimeInterval
    private let currencyRequestTimeout: TimeInterval
    private let startupTimeout: TimeInterval

    init(
        requestTimeout: TimeInterval = 3,
        currencyRequestTimeout: TimeInterval = 6,
        startupTimeout: TimeInterval = 20
    ) {
        self.requestTimeout = requestTimeout
        self.currencyRequestTimeout = currencyRequestTimeout
        self.startupTimeout = startupTimeout
        queue.async { [weak self] in
            try? self?.startIfNeeded()
        }
    }

    deinit {
        if process?.isRunning == true {
            process?.terminate()
        }
    }

    func evaluate(expression: String, precision: Int = 16) async throws -> EvaluationResult {
        let payload = try await perform(
            .evaluate(expression: expression, precision: precision)
        )
        return EvaluationResult(exact: payload.exact, approximate: payload.approx)
    }

    func convert(
        value: String,
        fromUnit: String,
        toUnit: String,
        precision: Int = 12
    ) async throws -> UnitConversionResult {
        let payload = try await perform(
            .convert(
                value: value,
                fromUnit: fromUnit,
                toUnit: toUnit,
                precision: precision
            )
        )
        guard let unit = payload.unit else {
            throw MathRuntimeError.invalidResponse
        }
        return UnitConversionResult(
            exact: payload.exact,
            approximate: payload.approx,
            runtimeUnit: unit,
            warnings: payload.warnings ?? []
        )
    }

    func convertCurrency(
        value: String,
        fromCurrency: String,
        toCurrency: String,
        precision: Int = 12,
        forceRefresh: Bool = false
    ) async throws -> CurrencyConversionResult {
        let payload = try await perform(
            .convertCurrency(
                value: value,
                fromCurrency: fromCurrency,
                toCurrency: toCurrency,
                precision: precision,
                forceRefresh: forceRefresh
            )
        )
        guard let approximate = payload.approx,
              let currency = payload.unit,
              let rate = payload.rate,
              let sourceURL = URL(string: rate.sourceURL),
              let checkedAt = Self.isoDate(rate.checkedAt),
              let expiresAt = Self.isoDate(rate.expiresAt),
              let state = CurrencyRateState(rawValue: rate.state)
        else {
            throw MathRuntimeError.invalidResponse
        }
        let publishedAt: Date?
        if let value = rate.publishedAt {
            guard let parsed = Self.isoDate(value) else {
                throw MathRuntimeError.invalidResponse
            }
            publishedAt = parsed
        } else {
            publishedAt = nil
        }
        let nextRefreshAttemptAt: Date?
        if let value = rate.nextRefreshAttemptAt {
            guard let parsed = Self.isoDate(value) else {
                throw MathRuntimeError.invalidResponse
            }
            nextRefreshAttemptAt = parsed
        } else {
            nextRefreshAttemptAt = nil
        }
        return CurrencyConversionResult(
            approximate: approximate,
            currency: currency,
            rate: CurrencyRateMetadata(
                sourceName: rate.sourceName,
                sourceShortName: rate.sourceShortName,
                sourceURL: sourceURL,
                rateDate: rate.rateDate,
                publishedAt: publishedAt,
                checkedAt: checkedAt,
                expiresAt: expiresAt,
                nextRefreshAttemptAt: nextRefreshAttemptAt,
                state: state,
                isCached: rate.isCached,
                refreshFailed: rate.refreshFailed,
                refreshDeferred: rate.refreshDeferred ?? false
            ),
            warnings: payload.warnings ?? []
        )
    }

    private func perform(_ operation: RuntimeOperation) async throws -> RuntimePayload {
        let revision = currentCancellationRevision()
        return try await withCheckedThrowingContinuation { continuation in
            queue.async { [self] in
                do {
                    continuation.resume(
                        returning: try performSynchronously(
                            operation,
                            cancellationRevision: revision
                        )
                    )
                } catch let error as MathRuntimeError {
                    continuation.resume(throwing: error)
                } catch {
                    continuation.resume(throwing: MathRuntimeError.invalidResponse)
                }
            }
        }
    }

    func cancelPendingEvaluation() {
        cancelPendingRequest()
    }

    func cancelPendingConversion() {
        cancelPendingRequest()
    }

    func cancelPendingCurrencyConversion() {
        cancelPendingRequest()
    }

    private func cancelPendingRequest() {
        cancellationLock.lock()
        cancellationRevision &+= 1
        cancellationLock.unlock()
    }

    private func performSynchronously(
        _ operation: RuntimeOperation,
        cancellationRevision: Int
    ) throws -> RuntimePayload {
        do {
            return try send(
                operation,
                cancellationRevision: cancellationRevision
            )
        } catch MathRuntimeError.invalidResponse {
            stopProcess()
            return try send(
                operation,
                cancellationRevision: cancellationRevision
            )
        }
    }

    private func send(
        _ operation: RuntimeOperation,
        cancellationRevision: Int
    ) throws -> RuntimePayload {
        try requireCurrent(cancellationRevision)
        try startIfNeeded()
        let requestID = UUID().uuidString
        let request = operation.request(id: requestID)
        var requestData = try JSONEncoder().encode(request)
        requestData.append(0x0A)
        guard let inputHandle else {
            throw MathRuntimeError.invalidResponse
        }
        do {
            try inputHandle.write(contentsOf: requestData)
        } catch {
            throw MathRuntimeError.invalidResponse
        }

        let payload = try JSONDecoder().decode(
            RuntimePayload.self,
            from: readLine(
                timeout: responseTimeout(for: operation),
                cancellationRevision: cancellationRevision
            )
        )
        guard payload.id == requestID else {
            throw MathRuntimeError.invalidResponse
        }
        guard payload.status == "ok" else {
            throw MathRuntimeError.operation(payload.error?.message ?? "Calculation failed.")
        }
        return payload
    }

    private func responseTimeout(for operation: RuntimeOperation) -> TimeInterval {
        switch operation {
        case .convertCurrency:
            currencyRequestTimeout
        case .evaluate, .convert:
            requestTimeout
        }
    }

    private static func isoDate(_ value: String) -> Date? {
        ISO8601DateFormatter().date(from: value)
    }

    private func startIfNeeded() throws {
        if process?.isRunning == true, inputHandle != nil, outputHandle != nil {
            return
        }
        stopProcess()

        let launch = try runtimeLaunch()

        let process = Process()
        let inputPipe = Pipe()
        let outputPipe = Pipe()
        process.executableURL = launch.executable
        process.currentDirectoryURL = launch.workingDirectory
        process.arguments = launch.arguments
        process.environment = ProcessInfo.processInfo.environment.merging(
            ["OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1"],
            uniquingKeysWith: { _, calculatorValue in calculatorValue }
        )
        process.standardInput = inputPipe
        process.standardOutput = outputPipe
        process.standardError = FileHandle.nullDevice

        do {
            try process.run()
        } catch {
            throw MathRuntimeError.runtimeNotInstalled
        }
        self.process = process
        inputHandle = inputPipe.fileHandleForWriting
        outputHandle = outputPipe.fileHandleForReading
        responseBuffer.removeAll(keepingCapacity: true)

        let ready = try JSONDecoder().decode(
            RuntimePayload.self,
            from: readLine(timeout: startupTimeout, cancellationRevision: nil)
        )
        guard ready.status == "ready" else {
            stopProcess()
            throw MathRuntimeError.invalidResponse
        }
    }

    private func readLine(timeout: TimeInterval, cancellationRevision: Int?) throws -> Data {
        let newline = Data([0x0A])
        let deadline = Date().addingTimeInterval(timeout)
        while true {
            if let cancellationRevision {
                do {
                    try requireCurrent(cancellationRevision)
                } catch {
                    stopProcess()
                    throw error
                }
            }
            if Date() >= deadline {
                stopProcess()
                throw MathRuntimeError.timedOut
            }
            if let range = responseBuffer.range(of: newline) {
                let line = responseBuffer.subdata(in: responseBuffer.startIndex..<range.lowerBound)
                responseBuffer.removeSubrange(responseBuffer.startIndex...range.lowerBound)
                return line
            }
            guard let outputHandle else {
                throw MathRuntimeError.invalidResponse
            }
            var descriptor = pollfd(
                fd: outputHandle.fileDescriptor,
                events: Int16(POLLIN | POLLHUP),
                revents: 0
            )
            let pollResult = Darwin.poll(&descriptor, 1, 25)
            if pollResult == 0 { continue }
            guard pollResult > 0 else { throw MathRuntimeError.invalidResponse }
            let chunk = outputHandle.availableData
            guard !chunk.isEmpty else { throw MathRuntimeError.invalidResponse }
            responseBuffer.append(chunk)
        }
    }

    private func currentCancellationRevision() -> Int {
        cancellationLock.lock()
        defer { cancellationLock.unlock() }
        return cancellationRevision
    }

    private func requireCurrent(_ revision: Int) throws {
        guard currentCancellationRevision() == revision else {
            throw MathRuntimeError.cancelled
        }
    }

    private func stopProcess() {
        try? inputHandle?.close()
        try? outputHandle?.close()
        if process?.isRunning == true {
            process?.terminate()
        }
        process = nil
        inputHandle = nil
        outputHandle = nil
        responseBuffer.removeAll(keepingCapacity: false)
    }

    private func runtimeLaunch() throws -> RuntimeLaunch {
        let fileManager = FileManager.default
        if let resources = Bundle.main.resourceURL {
            let bundledRuntime = resources.appending(
                path: "Runtime/zibetha-runtime/zibetha-runtime"
            )
            if fileManager.isExecutableFile(atPath: bundledRuntime.path) {
                return RuntimeLaunch(
                    executable: bundledRuntime,
                    arguments: ["app"],
                    workingDirectory: resources
                )
            }
        }

        var candidate = URL(fileURLWithPath: fileManager.currentDirectoryPath)
        for _ in 0..<8 {
            let python = candidate.appending(path: ".venv/bin/python")
            if fileManager.fileExists(atPath: candidate.appending(path: "pyproject.toml").path),
               fileManager.isExecutableFile(atPath: python.path)
            {
                return RuntimeLaunch(
                    executable: python,
                    arguments: ["-u", "-m", "zibetha.app_runtime"],
                    workingDirectory: candidate
                )
            }
            let parent = candidate.deletingLastPathComponent()
            if parent == candidate { break }
            candidate = parent
        }
        throw MathRuntimeError.runtimeNotInstalled
    }
}
