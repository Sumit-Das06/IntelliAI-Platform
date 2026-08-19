import XCTest

@testable import IntelliAI

/// Unit tests for the shared layer's PURE seams — the same laws the
/// Android suite pins, expressed in XCTest. No network, no microphone,
/// no Keychain entitlements: everything here runs on a bare simulator.
final class WavEncoderTests: XCTestCase {
    func testHeaderIsCanonical16kMonoPcm16() {
        let pcm = Data([0x01, 0x02, 0x03, 0x04])
        let wav = WavEncoder.wav(fromPCM: pcm)
        XCTAssertEqual(wav.count, 44 + 4)
        XCTAssertEqual(String(data: wav[0..<4], encoding: .ascii), "RIFF")
        XCTAssertEqual(String(data: wav[8..<12], encoding: .ascii), "WAVE")
        // sample rate at offset 24, little-endian
        let rate = wav[24..<28].withUnsafeBytes { $0.loadUnaligned(as: UInt32.self) }
        XCTAssertEqual(UInt32(littleEndian: rate), 16_000)
        let channels = wav[22..<24].withUnsafeBytes { $0.loadUnaligned(as: UInt16.self) }
        XCTAssertEqual(UInt16(littleEndian: channels), 1)
        let bits = wav[34..<36].withUnsafeBytes { $0.loadUnaligned(as: UInt16.self) }
        XCTAssertEqual(UInt16(littleEndian: bits), 16)
        XCTAssertEqual(wav.suffix(4), pcm)
    }

    func testDataChunkLengthMatchesPayload() {
        let pcm = Data(repeating: 0, count: 32_000) // 1 s of 16 kHz PCM16
        let wav = WavEncoder.wav(fromPCM: pcm)
        let length = wav[40..<44].withUnsafeBytes { $0.loadUnaligned(as: UInt32.self) }
        XCTAssertEqual(UInt32(littleEndian: length), 32_000)
    }
}

final class DictationLanguageTests: XCTestCase {
    func testApiTagsMatchThePublicContract() {
        XCTAssertNil(DictationLanguage.auto.apiTag) // Auto → field OMITTED
        XCTAssertEqual(DictationLanguage.english.apiTag, "en")
        XCTAssertEqual(DictationLanguage.hindi.apiTag, "hi")
        XCTAssertEqual(DictationLanguage.arabic.apiTag, "ar")
    }

    func testUnknownPreferenceFallsBackToAuto() {
        XCTAssertEqual(DictationLanguage.fromPreference(nil), .auto)
        XCTAssertEqual(DictationLanguage.fromPreference("corrupted"), .auto)
        XCTAssertEqual(DictationLanguage.fromPreference("hi"), .hindi)
    }
}

final class ServerAddressTests: XCTestCase {
    func testHttpsIsAlwaysAcceptable() {
        XCTAssertEqual(
            ServerAddress.validate("https://api.example.com", debugBuild: false), .ok
        )
    }

    func testReleaseRefusesCleartext() {
        XCTAssertEqual(
            ServerAddress.validate("http://api.example.com", debugBuild: false),
            .releaseUnsafe
        )
    }

    func testDebugMayReachLocalhostOnly() {
        XCTAssertEqual(ServerAddress.validate("http://localhost:8000", debugBuild: true), .ok)
        XCTAssertEqual(
            ServerAddress.validate("http://api.example.com", debugBuild: true), .releaseUnsafe
        )
    }

    func testGarbageIsMalformed() {
        XCTAssertEqual(ServerAddress.validate("not a url", debugBuild: true), .malformed)
        XCTAssertEqual(ServerAddress.validate("ftp://x", debugBuild: true), .malformed)
    }
}

final class KeyMaskingTests: XCTestCase {
    func testMaskShowsOnlyPrefixAndTail() {
        let masked = KeychainStore.masked("ik_live_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123")
        XCTAssertTrue(masked.hasPrefix("ik_live_"))
        XCTAssertTrue(masked.hasSuffix("0123"))
        XCTAssertFalse(masked.contains("ABCDEFGHIJKLMNOP"))
    }

    func testShortValuesAreFullyMasked() {
        XCTAssertEqual(KeychainStore.masked("shortkey"), "••••••••")
    }
}

final class MultipartTests: XCTestCase {
    func testAutoOmitsTheLanguageField() {
        let body = IntelliAIApiClient.multipartBody(
            boundary: "B", wav: Data([0x0]), language: nil
        )
        let text = String(decoding: body, as: UTF8.self)
        XCTAssertFalse(text.contains("name=\"language\""))
        XCTAssertTrue(text.contains("name=\"model\""))
        XCTAssertTrue(text.contains("intelliai-stt"))
    }

    func testExplicitLanguageTravels() {
        let body = IntelliAIApiClient.multipartBody(
            boundary: "B", wav: Data([0x0]), language: "hi"
        )
        let text = String(decoding: body, as: UTF8.self)
        XCTAssertTrue(text.contains("name=\"language\""))
        XCTAssertTrue(text.contains("hi"))
        XCTAssertTrue(text.contains("filename=\"dictation.wav\""))
    }
}

final class EnvelopeInterpretationTests: XCTestCase {
    private func response(
        status: Int, headers: [String: String] = [:]
    ) -> HTTPURLResponse {
        HTTPURLResponse(
            url: URL(string: "https://api.example.com/v1/audio/transcriptions")!,
            statusCode: status,
            httpVersion: "HTTP/1.1",
            headerFields: headers
        )!
    }

    func testSuccessCarriesTextAndSampleId() {
        let outcome = IntelliAIApiClient.interpret(
            response: response(status: 200, headers: ["X-IntelliAI-Sample": "smp_1"]),
            body: Data(#"{"text": "नमस्ते"}"#.utf8)
        )
        XCTAssertEqual(outcome, .success(.init(text: "नमस्ते", sampleId: "smp_1")))
    }

    func testEmptyTextIsNoSpeechNotSuccess() {
        let outcome = IntelliAIApiClient.interpret(
            response: response(status: 200), body: Data(#"{"text": "  "}"#.utf8)
        )
        XCTAssertEqual(outcome, .failure(.init(kind: .noSpeech)))
    }

    func testQuotaAndRateLimitShareStatusButDiffer() {
        // The 429 pair: error.type decides, never the status alone.
        let quota = IntelliAIApiClient.interpret(
            response: response(status: 429),
            body: Data(#"{"error": {"type": "quota_exceeded_error"}}"#.utf8)
        )
        XCTAssertEqual(quota, .failure(.init(kind: .quota)))
        let limited = IntelliAIApiClient.interpret(
            response: response(status: 429, headers: ["Retry-After": "7"]),
            body: Data(#"{"error": {"type": "rate_limit_error"}}"#.utf8)
        )
        XCTAssertEqual(limited, .failure(.init(kind: .rateLimited, retryAfterSeconds: 7)))
    }

    func testMissingVsBadKeyByErrorCode() {
        let missing = IntelliAIApiClient.interpret(
            response: response(status: 401),
            body: Data(
                #"{"error": {"type": "authentication_error", "code": "missing_api_key"}}"#.utf8
            )
        )
        XCTAssertEqual(missing, .failure(.init(kind: .noApiKey)))
        let bad = IntelliAIApiClient.interpret(
            response: response(status: 401),
            body: Data(#"{"error": {"type": "authentication_error", "code": "invalid"}}"#.utf8)
        )
        XCTAssertEqual(bad, .failure(.init(kind: .badApiKey)))
    }

    func testValidationMessagesSurfaceVerbatim() {
        let outcome = IntelliAIApiClient.interpret(
            response: response(status: 400),
            body: Data(
                #"{"error": {"type": "invalid_request_error", "message": "audio exceeds the 600s duration limit"}}"#
                    .utf8
            )
        )
        XCTAssertEqual(
            outcome,
            .failure(
                .init(kind: .rejected, serverMessage: "audio exceeds the 600s duration limit")
            )
        )
    }

    func testUnparseableServerErrorFallsBackByStatus() {
        let outcome = IntelliAIApiClient.interpret(
            response: response(status: 502), body: Data("<html>bad gateway</html>".utf8)
        )
        XCTAssertEqual(outcome, .failure(.init(kind: .server)))
    }
}

final class FailureWordingTests: XCTestCase {
    func testNoInternalNamesInAnyUserFacingMessage() {
        for kind: FailureKind in [
            .noApiKey, .noBaseUrl, .httpsRequired, .badApiKey, .quota, .rateLimited,
            .unavailable, .rejected, .noSpeech, .sampleUnavailable, .network, .server,
        ] {
            let message = FailureWording.message(for: kind, serverMessage: nil).lowercased()
            for marker in ["qwen", "whisper", "llama", "gguf", "ggml", "artifact"] {
                XCTAssertFalse(message.contains(marker), "\(kind): leaks \(marker)")
            }
        }
    }
}

final class SettingsStoreTests: XCTestCase {
    private func freshStore() -> SettingsStore {
        let suite = "test-\(UUID().uuidString)"
        return SettingsStore(defaults: UserDefaults(suiteName: suite)!)
    }

    func testLanguageRoundtripAndDefault() {
        let store = freshStore()
        XCTAssertEqual(store.language, .auto)
        store.language = .hindi
        XCTAssertEqual(store.language, .hindi)
    }

    func testContributionDefaultsOn() {
        let store = freshStore()
        XCTAssertTrue(store.contribute)
        store.contribute = false
        XCTAssertFalse(store.contribute)
    }

    func testCorrectionHandoffRoundtrip() {
        let store = freshStore()
        XCTAssertNil(store.lastCollected)
        store.recordCollected(sampleId: "smp_9", transcript: "नमस्ते")
        XCTAssertEqual(store.lastCollected?.sampleId, "smp_9")
        store.clearCollected()
        XCTAssertNil(store.lastCollected)
    }
}
