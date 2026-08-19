import Foundation

/// The keyboard's one network capability: POST /v1/audio/transcriptions
/// against the IntelliAI platform — the SAME public endpoint Web and
/// Android use; there is no iOS-specific backend. Thin by design:
/// multipart request, envelope-aware response handling, nothing else.
/// The platform's error contract branches on `error.type`/`error.code`,
/// NEVER on HTTP status alone: a quota 429 (retrying never helps) and a
/// rate-limit 429 (Retry-After, backoff helps) share a status code and
/// mean opposite things.
///
/// Privacy: the API key lives in the Authorization header and nowhere
/// else — never in logs, never in `ApiOutcome` messages, never in
/// errors. Audio bytes go into the request body and are not retained.
///
/// Mirrors the Android `IntelliAIApiClient` law for law:
/// timeouts 10 s connect-class / 150 s call cap, `language` omitted for
/// Auto, `X-IntelliAI-Contribution: off` sent only when contribution is
/// off, ONE bounded retry only for the retryable 503 family.
final class IntelliAIApiClient {
    static let clientHeader = "ios-keyboard/1.0"

    private let baseUrl: () -> String
    private let apiKey: () -> String?
    private let debugBuild: Bool
    private let session: URLSession

    init(
        baseUrl: @escaping () -> String,
        apiKey: @escaping () -> String?,
        debugBuild: Bool,
        session: URLSession? = nil
    ) {
        self.baseUrl = baseUrl
        self.apiKey = apiKey
        self.debugBuild = debugBuild
        if let session {
            self.session = session
        } else {
            let configuration = URLSessionConfiguration.ephemeral
            // Sized for dictation against a CPU inference backend: the
            // request phase fails fast, the response must outlast the
            // gateway's own runtime deadline so the SERVER decides
            // timeouts, not the phone. The resource timeout bounds the
            // worst case — nothing hangs forever.
            configuration.timeoutIntervalForRequest = 120
            configuration.timeoutIntervalForResource = 150
            configuration.urlCache = nil
            configuration.httpCookieStorage = nil
            self.session = URLSession(configuration: configuration)
        }
    }

    // MARK: - Transcription

    /// Transcribe one WAV utterance. `language == nil` means Auto: the
    /// field is OMITTED entirely and the server detects the language.
    func transcribe(
        wav: Data,
        language: String?,
        contribute: Bool
    ) async -> ApiOutcome {
        guard let key = usableKey() else { return .failure(.init(kind: .noApiKey)) }
        switch usableBase() {
        case .missing: return .failure(.init(kind: .noBaseUrl))
        case .releaseUnsafe: return .failure(.init(kind: .httpsRequired))
        case .ok(let base):
            var request = URLRequest(url: base.appendingPathComponent("v1/audio/transcriptions"))
            request.httpMethod = "POST"
            request.setValue("Bearer \(key)", forHTTPHeaderField: "Authorization")
            request.setValue(Self.clientHeader, forHTTPHeaderField: "X-IntelliAI-Client")
            // Opt out ONLY when contribution is off. Sending nothing when
            // on preserves the server's existing behavior (and never
            // widens collection beyond org consent).
            if !contribute {
                request.setValue("off", forHTTPHeaderField: "X-IntelliAI-Contribution")
            }
            let boundary = "intelliai-\(UUID().uuidString)"
            request.setValue(
                "multipart/form-data; boundary=\(boundary)",
                forHTTPHeaderField: "Content-Type"
            )
            request.httpBody = Self.multipartBody(
                boundary: boundary, wav: wav, language: language
            )

            let first = await executeSafely(request)
            // One bounded retry, only for the explicitly retryable 503
            // family. Never more than one; never for anything else.
            if case .failure(let failure) = first, failure.kind == .unavailable {
                let wait = min(max(failure.retryAfterSeconds ?? 1, 1), 5)
                try? await Task.sleep(nanoseconds: UInt64(wait) * 1_000_000_000)
                if Task.isCancelled { return first }
                return await executeSafely(request)
            }
            return first
        }
    }

    // MARK: - Correction

    /// Attach a human correction to a collected sample — the existing
    /// public endpoint, never an iOS-specific one. Called only when a
    /// transcription returned a sample id. The corrected text is sent
    /// EXACTLY as the user entered it — the server keeps
    /// original_transcript immutable and evolves current_transcript.
    /// No retry: a correction is a deliberate user act.
    func correct(sampleId: String, correctedText: String) async -> CorrectionOutcome {
        guard let key = usableKey() else { return .failure(.noApiKey) }
        switch usableBase() {
        case .missing: return .failure(.noBaseUrl)
        case .releaseUnsafe: return .failure(.httpsRequired)
        case .ok(let base):
            var request = URLRequest(
                url: base.appendingPathComponent("v1/audio/transcriptions/\(sampleId)/correction")
            )
            request.httpMethod = "POST"
            request.setValue("Bearer \(key)", forHTTPHeaderField: "Authorization")
            request.setValue(Self.clientHeader, forHTTPHeaderField: "X-IntelliAI-Client")
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.httpBody = try? JSONSerialization.data(
                withJSONObject: ["corrected_text": correctedText]
            )
            do {
                let (data, response) = try await session.data(for: request)
                return Self.interpretCorrection(response: response, body: data)
            } catch {
                return .failure(.network)
            }
        }
    }

    // MARK: - Internals

    private func usableKey() -> String? {
        guard let key = apiKey()?.trimmingCharacters(in: .whitespacesAndNewlines),
              !key.isEmpty else { return nil }
        return key
    }

    private enum BaseVerdict {
        case ok(URL)
        case missing
        case releaseUnsafe
    }

    private func usableBase() -> BaseVerdict {
        var base = baseUrl().trimmingCharacters(in: .whitespacesAndNewlines)
        while base.hasSuffix("/") { base.removeLast() }
        guard !base.isEmpty else { return .missing }
        switch ServerAddress.validate(base, debugBuild: debugBuild) {
        case .ok:
            guard let url = URL(string: base) else { return .missing }
            return .ok(url)
        case .malformed: return .missing
        case .releaseUnsafe: return .releaseUnsafe
        }
    }

    private func executeSafely(_ request: URLRequest) async -> ApiOutcome {
        do {
            let (data, response) = try await session.data(for: request)
            return Self.interpret(response: response, body: data)
        } catch {
            // Timeout, DNS, refused, offline, cancelled — one honest
            // bucket. The error text is deliberately dropped: raw socket
            // messages help nobody and can echo URLs.
            return .failure(.init(kind: .network))
        }
    }

    static func multipartBody(boundary: String, wav: Data, language: String?) -> Data {
        var body = Data()
        func field(_ name: String, _ value: String) {
            body.append(Data("--\(boundary)\r\n".utf8))
            body.append(
                Data("Content-Disposition: form-data; name=\"\(name)\"\r\n\r\n\(value)\r\n".utf8)
            )
        }
        field("model", "intelliai-stt")
        if let language { field("language", language) }
        body.append(Data("--\(boundary)\r\n".utf8))
        body.append(
            Data(
                (
                    "Content-Disposition: form-data; name=\"file\"; "
                        + "filename=\"dictation.wav\"\r\nContent-Type: audio/wav\r\n\r\n"
                ).utf8
            )
        )
        body.append(wav)
        body.append(Data("\r\n--\(boundary)--\r\n".utf8))
        return body
    }

    /// error.type is the contract; status is only the fallback for
    /// envelopes we cannot parse. Pure, unit-tested.
    static func interpret(response: URLResponse, body: Data) -> ApiOutcome {
        guard let http = response as? HTTPURLResponse else {
            return .failure(.init(kind: .network))
        }
        let json =
            (try? JSONSerialization.jsonObject(with: body)) as? [String: Any] ?? [:]
        if (200...299).contains(http.statusCode) {
            let text = (json["text"] as? String)?
                .trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
            if text.isEmpty { return .failure(.init(kind: .noSpeech)) }
            let sampleId = http.value(forHTTPHeaderField: "X-IntelliAI-Sample")
            return .success(.init(text: text, sampleId: sampleId))
        }

        let error = json["error"] as? [String: Any]
        let type = error?["type"] as? String ?? ""
        let code = error?["code"] as? String ?? ""
        let serverMessage = error?["message"] as? String
        let retryAfter = http.value(forHTTPHeaderField: "Retry-After").flatMap(Int.init)

        switch true {
        case type == "authentication_error":
            return .failure(.init(kind: code == "missing_api_key" ? .noApiKey : .badApiKey))
        case type == "quota_exceeded_error":
            return .failure(.init(kind: .quota))
        case type == "rate_limit_error":
            return .failure(.init(kind: .rateLimited, retryAfterSeconds: retryAfter))
        case type == "service_unavailable_error":
            return .failure(.init(kind: .unavailable, retryAfterSeconds: retryAfter))
        case type == "invalid_request_error" || type == "resource_not_found_error":
            // The platform writes these messages for humans and they
            // carry no secrets — surface them (e.g. which languages are
            // served).
            return .failure(.init(kind: .rejected, serverMessage: serverMessage))
        case http.statusCode == 401:
            return .failure(.init(kind: .badApiKey))
        case http.statusCode == 429:
            return .failure(.init(kind: .rateLimited, retryAfterSeconds: retryAfter))
        case (500...599).contains(http.statusCode):
            return .failure(.init(kind: .server))
        default:
            return .failure(.init(kind: .rejected))
        }
    }

    static func interpretCorrection(response: URLResponse, body: Data) -> CorrectionOutcome {
        guard let http = response as? HTTPURLResponse else { return .failure(.network) }
        if (200...299).contains(http.statusCode) { return .success }
        let json =
            (try? JSONSerialization.jsonObject(with: body)) as? [String: Any] ?? [:]
        let type = (json["error"] as? [String: Any])?["type"] as? String ?? ""
        switch type {
        case "authentication_error": return .failure(.badApiKey)
        // The sample is gone or belongs to another org (404, never
        // existence-disclosing): nothing here to correct.
        case "resource_not_found_error": return .failure(.sampleUnavailable)
        case "invalid_request_error": return .failure(.rejected)
        case "rate_limit_error": return .failure(.rateLimited)
        default:
            return .failure(http.statusCode == 401 ? .badApiKey : .server)
        }
    }
}

// MARK: - Outcomes (product terms; never internal model names)

enum ApiOutcome: Equatable {
    struct Success: Equatable {
        let text: String
        let sampleId: String?
    }

    struct Failure: Equatable {
        let kind: FailureKind
        var serverMessage: String? = nil
        var retryAfterSeconds: Int? = nil
    }

    case success(Success)
    case failure(Failure)
}

enum CorrectionOutcome: Equatable {
    case success
    case failure(FailureKind)
}

enum FailureKind: Equatable {
    case noApiKey // no key configured / server saw none
    case noBaseUrl // no (usable) server address configured
    case httpsRequired // release build pointed at cleartext or a dev host
    case badApiKey // invalid, revoked, or expired
    case quota // monthly allowance exhausted — retrying never helps
    case rateLimited // slow down; Retry-After says when
    case unavailable // 503 family — briefly retryable
    case rejected // the request itself was refused (validation, language…)
    case noSpeech // 200 with empty text: nothing recognizable was said
    case sampleUnavailable // the sample to correct no longer exists
    case network // could not reach IntelliAI at all
    case server // 5xx without a parseable envelope
}
