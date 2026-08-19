import Foundation

/// The dictation state machine — pure orchestration, injected seams,
/// mirroring Android's DictationController:
///
///     idle → recording → processing → idle
///
/// Laws it enforces (all unit-tested):
/// - the mic tap TOGGLES: tap while idle starts, tap while recording
///   stops-and-sends; taps while PROCESSING are ignored (duplicate-tap
///   protection — one in-flight request, never two);
/// - recording is capped at 60 s (the Android cap; well inside the
///   backend's ceiling) — the cap STOPS AND SENDS, it does not discard;
/// - the language is snapshotted when the request forms: changing the
///   setting mid-flight never changes an in-flight request;
/// - cancellation (keyboard dismissed) discards audio and abandons the
///   outcome — nothing is inserted afterwards;
/// - an empty recording is never sent.
@MainActor
final class DictationController {
    enum State: Equatable {
        case idle
        case recording
        case processing
    }

    struct Callbacks {
        var stateChanged: (State) -> Void = { _ in }
        var insertText: (String) -> Void = { _ in }
        var showFailure: (FailureKind, String?) -> Void = { _, _ in }
        var collected: (_ sampleId: String, _ transcript: String) -> Void = { _, _ in }
    }

    static let maxRecordingSeconds: TimeInterval = 60

    private let recorder: RecorderSeam
    private let transcribe: (Data, String?, Bool) async -> ApiOutcome
    private let settings: SettingsStore
    private var callbacks: Callbacks
    private var capTask: Task<Void, Never>?
    private var requestTask: Task<Void, Never>?

    private(set) var state: State = .idle {
        didSet { callbacks.stateChanged(state) }
    }

    init(
        recorder: RecorderSeam,
        transcribe: @escaping (Data, String?, Bool) async -> ApiOutcome,
        settings: SettingsStore,
        callbacks: Callbacks
    ) {
        self.recorder = recorder
        self.transcribe = transcribe
        self.settings = settings
        self.callbacks = callbacks
        self.recorder.onInterruption = { [weak self] in
            Task { @MainActor [weak self] in self?.finishRecordingAndSend() }
        }
    }

    /// The mic key. Idle → start; recording → stop-and-send;
    /// processing → ignored (duplicate-tap protection).
    func micTapped() {
        switch state {
        case .idle: startRecording()
        case .recording: finishRecordingAndSend()
        case .processing: break
        }
    }

    /// Keyboard dismissed / view gone: discard everything in flight.
    func cancel() {
        capTask?.cancel()
        capTask = nil
        requestTask?.cancel()
        requestTask = nil
        recorder.cancel()
        state = .idle
    }

    private func startRecording() {
        do {
            try recorder.start()
        } catch {
            callbacks.showFailure(.rejected, "Microphone unavailable. Open IntelliAI to grant access.")
            return
        }
        state = .recording
        capTask = Task { [weak self] in
            try? await Task.sleep(
                nanoseconds: UInt64(Self.maxRecordingSeconds * 1_000_000_000)
            )
            guard !Task.isCancelled else { return }
            await MainActor.run { [weak self] in
                if self?.state == .recording { self?.finishRecordingAndSend() }
            }
        }
    }

    private func finishRecordingAndSend() {
        guard state == .recording else { return }
        capTask?.cancel()
        capTask = nil
        let wav = recorder.stop()
        // Header-only WAV = nothing was captured; don't waste a request.
        guard wav.count > 44 else {
            state = .idle
            return
        }
        state = .processing
        // Snapshot BOTH settings now: an in-flight request never changes.
        let language = settings.language.apiTag
        let contribute = settings.contribute
        requestTask = Task { [weak self] in
            guard let self else { return }
            let outcome = await self.transcribe(wav, language, contribute)
            guard !Task.isCancelled else { return }
            await MainActor.run {
                self.requestTask = nil
                self.state = .idle
                switch outcome {
                case .success(let success):
                    self.callbacks.insertText(success.text)
                    if let sampleId = success.sampleId {
                        self.callbacks.collected(sampleId, success.text)
                    }
                case .failure(let failure):
                    self.callbacks.showFailure(failure.kind, failure.serverMessage)
                }
            }
        }
    }
}

/// The recorder seam: the real `WavRecorder` in the extension, a fake
/// in unit tests.
protocol RecorderSeam: AnyObject {
    var onInterruption: (() -> Void)? { get set }
    func start() throws
    func stop() -> Data
    func cancel()
}

extension WavRecorder: RecorderSeam {}

/// Product-safe wording for every failure — never an internal model,
/// engine, or infrastructure name. Pure, unit-tested for leak markers.
enum FailureWording {
    static func message(for kind: FailureKind, serverMessage: String?) -> String {
        switch kind {
        case .noApiKey: return "Add your IntelliAI API key in the IntelliAI app."
        case .noBaseUrl: return "Set the IntelliAI server address in the IntelliAI app."
        case .httpsRequired: return "This server address needs HTTPS."
        case .badApiKey: return "Your API key was not accepted. Check it in the IntelliAI app."
        case .quota: return "Your monthly usage allowance is used up."
        case .rateLimited: return "Too many requests — try again in a moment."
        case .unavailable: return "IntelliAI is briefly busy. Try again."
        case .rejected: return serverMessage ?? "IntelliAI could not process this request."
        case .noSpeech: return "No speech detected."
        case .sampleUnavailable: return "This transcription can no longer be corrected."
        case .network: return "Could not reach IntelliAI. Check your connection."
        case .server: return "IntelliAI hit a problem. Try again."
        }
    }
}
