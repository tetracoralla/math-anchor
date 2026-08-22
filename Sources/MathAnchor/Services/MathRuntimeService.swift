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

        var abortsWorkerWhenCancelled: Bool {
            switch self {
            case .evaluate:
                true
            case .convert, .convertCurrency:
                false
            }
        }

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
        let code: String?
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

    private final class PendingRequest {
        let continuation: CheckedContinuation<RuntimePayload, Error>
        let abortsWorkerWhenCancelled: Bool

        init(
            continuation: CheckedContinuation<RuntimePayload, Error>,
            abortsWorkerWhenCancelled: Bool
        ) {
            self.continuation = continuation
            self.abortsWorkerWhenCancelled = abortsWorkerWhenCancelled
        }
    }

    // Lifecycle (launch, stop, request writes) is serialized on writeQueue.
    // The reader loop owns stdout. Everything else reaches shared state only
    // through `lock`, so calculator, unit, and currency requests proceed
    // concurrently against one warm worker and are matched by request id.
    private let writeQueue = DispatchQueue(
        label: "com.openadam.mathanchor.runtime.write",
        qos: .userInitiated
    )
    private let readerQueue = DispatchQueue(
        label: "com.openadam.mathanchor.runtime.read",
        qos: .userInitiated
    )
    private let lock = NSLock()
    private var process: Process?
    private var inputHandle: FileHandle?
    private var outputHandle: FileHandle?
    private var responseBuffer = Data()
    private var pendingRequests: [String: PendingRequest] = [:]
    private var startWaiters: [CheckedContinuation<Void, Error>] = []
    private var currentGeneration = 0
    private var readerGeneration = 0
    private var lastLineAt = Date()
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
        writeQueue.async { [weak self] in
            try? self?.launchProcessOnQueue()
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

    // Cheap conversion requests are debounced and may finish harmlessly after
    // their result becomes stale, so cancelling them must not turn the next
    // keystroke into a cold start. Expression evaluation is different: it can
    // occupy the app runtime until its ten-second in-process bound. Abort that
    // worker so an edited/replaced calculation does not block the next one.
    func cancelPendingEvaluation() {
        cancelPendingRequestsThatAbortWorker()
    }
    func cancelPendingConversion() {}
    func cancelPendingCurrencyConversion() {}

    private func perform(_ operation: RuntimeOperation) async throws -> RuntimePayload {
        do {
            try await ensureStarted()
            return try await send(operation)
        } catch MathRuntimeError.invalidResponse {
            // Protocol failure or worker death: rebuild once and retry.
            stopProcess()
            try await ensureStarted()
            return try await send(operation)
        }
    }

    private func ensureStarted() async throws {
        try await withCheckedThrowingContinuation { continuation in
            writeQueue.async { [self] in
                lock.lock()
                let processRunning = process?.isRunning == true
                lock.unlock()

                if processRunning {
                    // A launch whose ready handshake is still in flight must
                    // not be killed and restarted by a concurrent caller;
                    // share it. (A failed handshake clears the process, and
                    // the startup timeout bounds the wait.)
                    lock.lock()
                    // The handshake may have completed while this waiter
                    // registered; never park a resolved generation.
                    if readerGeneration == currentGeneration {
                        lock.unlock()
                        continuation.resume()
                        return
                    }
                    startWaiters.append(continuation)
                    lock.unlock()
                    return
                }

                do {
                    try launchProcessOnQueue()
                } catch {
                    continuation.resume(throwing: error)
                    return
                }
                lock.lock()
                if readerGeneration == currentGeneration {
                    lock.unlock()
                    continuation.resume()
                    return
                }
                startWaiters.append(continuation)
                lock.unlock()
            }
        }
    }

    private func send(_ operation: RuntimeOperation) async throws -> RuntimePayload {
        let requestID = UUID().uuidString
        let request = operation.request(id: requestID)
        var encodedRequest = try JSONEncoder().encode(request)
        encodedRequest.append(0x0A)
        // Capture an immutable value in the concurrent write closure. Swift 6
        // correctly warns when a mutable local is captured across queues even
        // if this function never mutates it again.
        let requestData = encodedRequest
        let timeout = responseTimeout(for: operation)

        return try await withTaskCancellationHandler {
            try await withCheckedThrowingContinuation { continuation in
                lock.lock()
                if Task.isCancelled {
                    lock.unlock()
                    continuation.resume(throwing: MathRuntimeError.cancelled)
                    return
                }
                pendingRequests[requestID] = PendingRequest(
                    continuation: continuation,
                    abortsWorkerWhenCancelled: operation.abortsWorkerWhenCancelled
                )
                let handle = inputHandle
                lock.unlock()

                writeQueue.async { [self] in
                    guard let handle else {
                        failRequest(requestID, error: .invalidResponse)
                        return
                    }
                    do {
                        try handle.write(contentsOf: requestData)
                    } catch {
                        failRequest(requestID, error: .invalidResponse)
                        return
                    }
                    scheduleRequestTimeout(id: requestID, timeout: timeout)
                }
            }
        } onCancel: { [self] in
            cancelRequest(requestID)
        }
    }

    private func scheduleRequestTimeout(id: String, timeout: TimeInterval) {
        DispatchQueue.global(qos: .userInitiated).asyncAfter(deadline: .now() + timeout) { [weak self] in
            guard let self else { return }
            lock.lock()
            guard let pending = pendingRequests.removeValue(forKey: id) else {
                lock.unlock()
                return
            }
            let lastLine = lastLineAt
            let remainingPending = !pendingRequests.isEmpty
            lock.unlock()

            pending.continuation.resume(throwing: MathRuntimeError.timedOut)
            // A worker that has produced nothing within the whole window is
            // treated as hung and rebuilt. A worker that is still answering
            // other requests (for example one left behind by an abandoned
            // slow call) stays warm; its own in-process bound ends that work.
            if Date().timeIntervalSince(lastLine) >= timeout {
                if remainingPending {
                    // Other requests are still waiting on this reader; let
                    // their own deadlines decide before tearing it down.
                    return
                }
                stopProcess()
            }
        }
    }

    private func responseTimeout(for operation: RuntimeOperation) -> TimeInterval {
        switch operation {
        case .convertCurrency:
            currencyRequestTimeout
        case .evaluate, .convert:
            requestTimeout
        }
    }

    // ISO8601DateFormatter is documented thread-safe; `nonisolated(unsafe)`
    // suppresses the Sendable diagnostic for the shared instance.
    private nonisolated(unsafe) static let isoDateFormatter = ISO8601DateFormatter()

    private static func isoDate(_ value: String) -> Date? {
        isoDateFormatter.date(from: value)
    }

    // MARK: Process lifecycle. Must run on writeQueue unless noted.

    /// Lock must be held. True once this generation's reader saw "ready".
    private var hasResolvedReady: Bool {
        readerGeneration == currentGeneration
    }

    private func launchProcessOnQueue() throws {
        stopProcessOnQueue()
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

        lock.lock()
        self.process = process
        inputHandle = inputPipe.fileHandleForWriting
        outputHandle = outputPipe.fileHandleForReading
        responseBuffer.removeAll(keepingCapacity: true)
        currentGeneration += 1
        let generation = currentGeneration
        lastLineAt = Date()
        lock.unlock()

        startReader(generation: generation)
        scheduleStartupTimeout(generation: generation, timeout: startupTimeout)
    }

    private func scheduleStartupTimeout(generation: Int, timeout: TimeInterval) {
        DispatchQueue.global(qos: .userInitiated).asyncAfter(deadline: .now() + timeout) { [weak self] in
            guard let self else { return }
            lock.lock()
            let stillStarting = currentGeneration == generation && !hasResolvedReady
            let waiters = stillStarting ? drainStartWaitersLocked() : []
            lock.unlock()
            guard stillStarting else { return }
            resumeWaiters(waiters, error: MathRuntimeError.timedOut)
            stopProcess()
        }
    }

    private func startReader(generation: Int) {
        readerQueue.async { [self] in
            var expectingReady = true
            while true {
                lock.lock()
                let current = currentGeneration
                let handle = outputHandle
                let alive = current == generation && process?.isRunning == true
                lock.unlock()

                guard alive, let handle else {
                    self.handleReaderTerminated(generation: generation)
                    return
                }

                var descriptor = pollfd(
                    fd: handle.fileDescriptor,
                    events: Int16(POLLIN | POLLHUP),
                    revents: 0
                )
                let pollResult = Darwin.poll(&descriptor, 1, 25)
                if pollResult == 0 { continue }
                guard pollResult > 0 else {
                    self.handleReaderTerminated(generation: generation)
                    return
                }
                let chunk = handle.availableData
                guard !chunk.isEmpty else {
                    self.handleReaderTerminated(generation: generation)
                    return
                }

                lock.lock()
                responseBuffer.append(chunk)
                lastLineAt = Date()
                var lines: [Data] = []
                let newline = Data([0x0A])
                while let range = responseBuffer.range(of: newline) {
                    lines.append(responseBuffer.subdata(in: responseBuffer.startIndex..<range.lowerBound))
                    responseBuffer.removeSubrange(responseBuffer.startIndex...range.lowerBound)
                }
                lock.unlock()

                for line in lines {
                    if expectingReady {
                        guard let readyPayload = Self.decodePayload(line),
                              readyPayload.status == "ready"
                        else {
                            self.handleStartupProtocolFailure(generation: generation)
                            return
                        }
                        expectingReady = false
                        self.resolveReady(generation: generation)
                    } else if let payload = Self.decodePayload(line) {
                        self.dispatch(payload)
                    } else {
                        // A malformed line is a protocol failure, not silence.
                        // Waiting for every request timer would leave the app
                        // unusable longer and misreport the failure as timeout.
                        self.handleRuntimeProtocolFailure(generation: generation)
                        return
                    }
                }
            }
        }
    }

    private func dispatch(_ payload: RuntimePayload) {
        lock.lock()
        let pending = payload.id.flatMap { pendingRequests.removeValue(forKey: $0) }
        lock.unlock()
        guard let pending else { return }
        guard payload.status == "ok" else {
            pending.continuation.resume(
                throwing: MathRuntimeError.fromRuntime(code: payload.error?.code)
            )
            return
        }
        pending.continuation.resume(returning: payload)
    }

    private func resolveReady(generation: Int) {
        lock.lock()
        guard currentGeneration == generation else {
            lock.unlock()
            return
        }
        readerGeneration = generation
        let waiters = drainStartWaitersLocked()
        lock.unlock()
        resumeWaiters(waiters, error: nil)
    }

    private func handleStartupProtocolFailure(generation: Int) {
        lock.lock()
        let stale = currentGeneration == generation
        let waiters = stale ? drainStartWaitersLocked() : []
        lock.unlock()
        if stale {
            resumeWaiters(waiters, error: MathRuntimeError.invalidResponse)
            stopProcess()
        }
    }

    private func handleReaderTerminated(generation: Int) {
        lock.lock()
        let stale = currentGeneration == generation
        let waiters = stale ? drainStartWaitersLocked() : []
        let pending = stale ? drainPendingRequestsLocked() : [:]
        lock.unlock()
        guard stale else { return }
        resumeWaiters(waiters, error: MathRuntimeError.invalidResponse)
        for request in pending.values {
            request.continuation.resume(throwing: MathRuntimeError.invalidResponse)
        }
        stopProcess()
    }

    private func handleRuntimeProtocolFailure(generation: Int) {
        lock.lock()
        let stale = currentGeneration == generation
        let pending = stale ? drainPendingRequestsLocked() : [:]
        lock.unlock()
        guard stale else { return }
        for request in pending.values {
            request.continuation.resume(throwing: MathRuntimeError.invalidResponse)
        }
        stopProcess()
    }

    private func failRequest(_ id: String, error: MathRuntimeError) {
        lock.lock()
        let pending = pendingRequests.removeValue(forKey: id)
        lock.unlock()
        pending?.continuation.resume(throwing: error)
    }

    private func cancelRequest(_ id: String) {
        lock.lock()
        let pending = pendingRequests.removeValue(forKey: id)
        lock.unlock()
        guard let pending else { return }
        pending.continuation.resume(throwing: MathRuntimeError.cancelled)
        if pending.abortsWorkerWhenCancelled {
            stopProcess()
        }
    }

    private func cancelPendingRequestsThatAbortWorker() {
        lock.lock()
        let cancelled = pendingRequests.filter { $0.value.abortsWorkerWhenCancelled }
        for id in cancelled.keys {
            pendingRequests.removeValue(forKey: id)
        }
        lock.unlock()
        guard !cancelled.isEmpty else { return }
        for request in cancelled.values {
            request.continuation.resume(throwing: MathRuntimeError.cancelled)
        }
        stopProcess()
    }

    private func drainStartWaitersLocked() -> [CheckedContinuation<Void, Error>] {
        let waiters = startWaiters
        startWaiters.removeAll()
        return waiters
    }

    private func drainPendingRequestsLocked() -> [String: PendingRequest] {
        let pending = pendingRequests
        pendingRequests.removeAll()
        return pending
    }

    private func resumeWaiters(
        _ waiters: [CheckedContinuation<Void, Error>],
        error: Error?
    ) {
        for waiter in waiters {
            if let error {
                waiter.resume(throwing: error)
            } else {
                waiter.resume()
            }
        }
    }

    private static func decodePayload(_ data: Data) -> RuntimePayload? {
        try? JSONDecoder().decode(RuntimePayload.self, from: data)
    }

    /// Safe to call from any queue: teardown is serialized onto writeQueue.
    private func stopProcess() {
        writeQueue.async { [self] in
            stopProcessOnQueue()
        }
    }

    private func stopProcessOnQueue() {
        lock.lock()
        let input = inputHandle
        let output = outputHandle
        let runningProcess = process
        process = nil
        inputHandle = nil
        outputHandle = nil
        responseBuffer.removeAll(keepingCapacity: false)
        let waiters = drainStartWaitersLocked()
        let pending = drainPendingRequestsLocked()
        lock.unlock()

        resumeWaiters(waiters, error: MathRuntimeError.invalidResponse)
        for request in pending.values {
            request.continuation.resume(throwing: MathRuntimeError.invalidResponse)
        }
        try? input?.close()
        try? output?.close()
        if runningProcess?.isRunning == true {
            runningProcess?.terminate()
        }
    }

    private func runtimeLaunch() throws -> RuntimeLaunch {
        let fileManager = FileManager.default
        if let resources = Bundle.main.resourceURL {
            let bundledRuntime = resources.appending(
                path: "Runtime/math-anchor-runtime/math-anchor-runtime"
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
                    arguments: ["-u", "-m", "math_anchor.app_runtime"],
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
