import AVFoundation
import Foundation

/// Microphone capture: 16 kHz / mono / PCM16 via AVAudioEngine, the
/// iOS equivalent of Android's AudioRecord path. The engine's native
/// input format is converted on the fly to the canonical rate, so the
/// bytes shipped to the platform match the Android client's exactly.
///
/// iOS specifics, handled here:
/// - The AUDIO SESSION is configured `.record` with `.duckOthers`; it
///   deactivates on stop so music resumes.
/// - INTERRUPTIONS (calls, Siri) stop the recording cleanly — the
///   partial audio is returned, never lost, never half-captured.
/// - The MICROPHONE PERMISSION prompt cannot be presented by a keyboard
///   extension; the container app owns the grant
///   (`AVAudioApplication.requestRecordPermission`). This class only
///   checks the already-granted state and fails honestly otherwise.
final class WavRecorder {
    enum RecorderError: Error {
        case permissionDenied
        case engineUnavailable
    }

    private let engine = AVAudioEngine()
    private var pcm = Data()
    private let lock = NSLock()
    private var interruptionObserver: NSObjectProtocol?
    private(set) var isRecording = false

    var onInterruption: (() -> Void)?

    static var permissionGranted: Bool {
        if #available(iOS 17.0, *) {
            return AVAudioApplication.shared.recordPermission == .granted
        }
        return AVAudioSession.sharedInstance().recordPermission == .granted
    }

    func start() throws {
        guard Self.permissionGranted else { throw RecorderError.permissionDenied }
        guard !isRecording else { return }

        let session = AVAudioSession.sharedInstance()
        try session.setCategory(.record, mode: .measurement, options: [.duckOthers])
        try session.setActive(true, options: [])

        let input = engine.inputNode
        let inputFormat = input.outputFormat(forBus: 0)
        guard inputFormat.sampleRate > 0 else { throw RecorderError.engineUnavailable }
        guard
            let targetFormat = AVAudioFormat(
                commonFormat: .pcmFormatInt16,
                sampleRate: Double(WavEncoder.sampleRateHz),
                channels: 1,
                interleaved: true
            ),
            let converter = AVAudioConverter(from: inputFormat, to: targetFormat)
        else { throw RecorderError.engineUnavailable }

        lock.lock()
        pcm.removeAll(keepingCapacity: true)
        lock.unlock()

        input.installTap(onBus: 0, bufferSize: 4096, format: inputFormat) {
            [weak self] buffer, _ in
            guard let self else { return }
            let ratio = targetFormat.sampleRate / inputFormat.sampleRate
            let capacity = AVAudioFrameCount(Double(buffer.frameLength) * ratio) + 64
            guard
                let converted = AVAudioPCMBuffer(
                    pcmFormat: targetFormat, frameCapacity: capacity
                )
            else { return }
            var consumed = false
            converter.convert(to: converted, error: nil) { _, status in
                if consumed {
                    status.pointee = .noDataNow
                    return nil
                }
                consumed = true
                status.pointee = .haveData
                return buffer
            }
            guard converted.frameLength > 0, let channel = converted.int16ChannelData else {
                return
            }
            let bytes = Data(
                bytes: channel[0], count: Int(converted.frameLength) * MemoryLayout<Int16>.size
            )
            self.lock.lock()
            self.pcm.append(bytes)
            self.lock.unlock()
        }

        interruptionObserver = NotificationCenter.default.addObserver(
            forName: AVAudioSession.interruptionNotification,
            object: session,
            queue: .main
        ) { [weak self] notification in
            let raw = notification.userInfo?[AVAudioSessionInterruptionTypeKey] as? UInt
            if raw == AVAudioSession.InterruptionType.began.rawValue {
                self?.onInterruption?()
            }
        }

        engine.prepare()
        try engine.start()
        isRecording = true
    }

    /// Stop and return the captured PCM16 as a WAV. Safe to call when
    /// not recording (returns whatever was captured, possibly empty).
    func stop() -> Data {
        if isRecording {
            engine.inputNode.removeTap(onBus: 0)
            engine.stop()
            isRecording = false
        }
        if let observer = interruptionObserver {
            NotificationCenter.default.removeObserver(observer)
            interruptionObserver = nil
        }
        try? AVAudioSession.sharedInstance().setActive(
            false, options: [.notifyOthersOnDeactivation]
        )
        lock.lock()
        let captured = pcm
        pcm.removeAll(keepingCapacity: false)
        lock.unlock()
        return WavEncoder.wav(fromPCM: captured)
    }

    /// Discard everything: for cancellation and keyboard dismissal —
    /// no audio is retained anywhere.
    func cancel() {
        _ = stop()
    }
}
