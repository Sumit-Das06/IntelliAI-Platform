import XCTest

@testable import IntelliAI

/// The dictation state machine's laws, driven through fakes — the same
/// pins the Android suite holds: toggle semantics, duplicate-tap
/// protection, empty-recording suppression, settings snapshotting, and
/// cancellation abandoning the outcome.
@MainActor
final class DictationControllerTests: XCTestCase {
    private final class FakeRecorder: RecorderSeam {
        var onInterruption: (() -> Void)?
        var wavToReturn = WavEncoder.wav(fromPCM: Data(repeating: 0, count: 3200))
        var started = 0
        var cancelled = 0

        func start() throws { started += 1 }
        func stop() -> Data { wavToReturn }
        func cancel() { cancelled += 1 }
    }

    private func store() -> SettingsStore {
        SettingsStore(defaults: UserDefaults(suiteName: "test-\(UUID().uuidString)")!)
    }

    func testTapTogglesAndSendsOnce() async {
        let recorder = FakeRecorder()
        let settings = store()
        var requests = 0
        var inserted: [String] = []
        let gate = expectation(description: "request completed")
        let controller = DictationController(
            recorder: recorder,
            transcribe: { _, _, _ in
                requests += 1
                return .success(.init(text: "नमस्ते", sampleId: nil))
            },
            settings: settings,
            callbacks: .init(
                stateChanged: { state in if state == .idle, requests > 0 { gate.fulfill() } },
                insertText: { inserted.append($0) }
            )
        )
        controller.micTapped() // idle → recording
        XCTAssertEqual(controller.state, .recording)
        controller.micTapped() // recording → processing (send)
        await fulfillment(of: [gate], timeout: 2)
        XCTAssertEqual(requests, 1)
        XCTAssertEqual(inserted, ["नमस्ते"])
        XCTAssertEqual(controller.state, .idle)
    }

    func testTapsWhileProcessingAreIgnored() async {
        let recorder = FakeRecorder()
        var requests = 0
        let release = expectation(description: "released")
        let controller = DictationController(
            recorder: recorder,
            transcribe: { _, _, _ in
                requests += 1
                try? await Task.sleep(nanoseconds: 200_000_000)
                release.fulfill()
                return .failure(.init(kind: .network))
            },
            settings: store(),
            callbacks: .init()
        )
        controller.micTapped()
        controller.micTapped() // → processing
        controller.micTapped() // ignored
        controller.micTapped() // ignored
        await fulfillment(of: [release], timeout: 2)
        XCTAssertEqual(requests, 1, "duplicate taps must never produce a second request")
        XCTAssertEqual(recorder.started, 1)
    }

    func testEmptyRecordingIsNeverSent() {
        let recorder = FakeRecorder()
        recorder.wavToReturn = WavEncoder.wav(fromPCM: Data()) // header only
        var requests = 0
        let controller = DictationController(
            recorder: recorder,
            transcribe: { _, _, _ in
                requests += 1
                return .failure(.init(kind: .network))
            },
            settings: store(),
            callbacks: .init()
        )
        controller.micTapped()
        controller.micTapped()
        XCTAssertEqual(requests, 0)
        XCTAssertEqual(controller.state, .idle)
    }

    func testLanguageIsSnapshottedAtSendTime() async {
        let settings = store()
        settings.language = .hindi
        var sent: [String?] = []
        let gate = expectation(description: "sent")
        let controller = DictationController(
            recorder: FakeRecorder(),
            transcribe: { _, language, _ in
                sent.append(language)
                gate.fulfill()
                return .failure(.init(kind: .network))
            },
            settings: settings,
            callbacks: .init()
        )
        controller.micTapped()
        controller.micTapped() // snapshot happens HERE
        settings.language = .english // must not affect the in-flight request
        await fulfillment(of: [gate], timeout: 2)
        XCTAssertEqual(sent, ["hi"])
    }

    func testCancellationAbandonsTheOutcome() async {
        var inserted: [String] = []
        let started = expectation(description: "request started")
        let controller = DictationController(
            recorder: FakeRecorder(),
            transcribe: { _, _, _ in
                started.fulfill()
                try? await Task.sleep(nanoseconds: 500_000_000)
                return .success(.init(text: "late", sampleId: nil))
            },
            settings: store(),
            callbacks: .init(insertText: { inserted.append($0) })
        )
        controller.micTapped()
        controller.micTapped()
        await fulfillment(of: [started], timeout: 2)
        controller.cancel() // keyboard dismissed mid-flight
        try? await Task.sleep(nanoseconds: 700_000_000)
        XCTAssertTrue(inserted.isEmpty, "a cancelled dictation must insert nothing")
        XCTAssertEqual(controller.state, .idle)
    }
}
