import UIKit

/// The IntelliAI custom keyboard: minimal typing + one-tap dictation
/// against the SAME IntelliAI backend as Web and Android.
///
/// Responsibilities (and nothing more): render keys, run the dictation
/// state machine, insert text through `textDocumentProxy` — iOS's
/// native input seam. Settings and the API key are READ here (App
/// Group + shared Keychain); they are only ever WRITTEN by the
/// container app.
///
/// iOS specifics honored:
/// - `textDocumentProxy.insertText` handles cursor position natively;
///   a leading space is added only when the character before the
///   cursor needs one (mirrors the Android commit law).
/// - Without Full Access there is no network: the mic key shows an
///   honest message instead of failing opaquely.
/// - `viewWillDisappear` cancels recording AND the in-flight request —
///   nothing is inserted into a field the user has left.
final class KeyboardViewController: UIInputViewController {
    private var keyboardView: KeyboardView!
    private var controller: DictationController?
    private let settings = SettingsStore()
    private let keychain = KeychainStore()

    override func viewDidLoad() {
        super.viewDidLoad()

        let debugBuild: Bool
        #if DEBUG
            debugBuild = true
        #else
            debugBuild = false
        #endif
        let client = IntelliAIApiClient(
            baseUrl: { [settings] in settings.serverAddress },
            apiKey: { [keychain] in keychain.read() },
            debugBuild: debugBuild
        )

        keyboardView = KeyboardView(frame: .zero)
        keyboardView.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(keyboardView)
        NSLayoutConstraint.activate([
            keyboardView.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            keyboardView.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            keyboardView.topAnchor.constraint(equalTo: view.topAnchor),
            keyboardView.bottomAnchor.constraint(equalTo: view.bottomAnchor),
            keyboardView.heightAnchor.constraint(equalToConstant: 240),
        ])

        controller = DictationController(
            recorder: WavRecorder(),
            transcribe: { wav, language, contribute in
                await client.transcribe(wav: wav, language: language, contribute: contribute)
            },
            settings: settings,
            callbacks: .init(
                stateChanged: { [weak self] state in self?.keyboardView.render(state: state) },
                insertText: { [weak self] text in self?.commit(text) },
                showFailure: { [weak self] kind, serverMessage in
                    self?.keyboardView.showStatus(
                        FailureWording.message(for: kind, serverMessage: serverMessage)
                    )
                },
                collected: { [settings] sampleId, transcript in
                    // Correction handoff: the container app offers
                    // "Improve this transcription" for the last
                    // collected sample. Ids only — never audio.
                    settings.recordCollected(sampleId: sampleId, transcript: transcript)
                }
            )
        )

        keyboardView.onKey = { [weak self] key in self?.handle(key) }
        keyboardView.render(language: settings.language)
    }

    override func viewWillAppear(_ animated: Bool) {
        super.viewWillAppear(animated)
        // The language may have changed in the container app.
        keyboardView.render(language: settings.language)
        if !hasFullAccess {
            keyboardView.showStatus("Allow Full Access in Settings to use dictation.")
        }
    }

    override func viewWillDisappear(_ animated: Bool) {
        controller?.cancel()
        super.viewWillDisappear(animated)
    }

    private func handle(_ key: KeyboardView.Key) {
        switch key {
        case .character(let text):
            textDocumentProxy.insertText(text)
        case .space:
            textDocumentProxy.insertText(" ")
        case .backspace:
            textDocumentProxy.deleteBackward()
        case .returnKey:
            textDocumentProxy.insertText("\n")
        case .nextKeyboard:
            advanceToNextInputMode()
        case .cycleLanguage:
            let all = DictationLanguage.allCases
            let index = all.firstIndex(of: settings.language) ?? 0
            settings.language = all[(index + 1) % all.count]
            keyboardView.render(language: settings.language)
        case .microphone:
            guard hasFullAccess else {
                keyboardView.showStatus("Allow Full Access in Settings to use dictation.")
                return
            }
            guard WavRecorder.permissionGranted else {
                keyboardView.showStatus("Open the IntelliAI app to allow the microphone.")
                return
            }
            controller?.micTapped()
        }
    }

    /// Insert a transcript at the cursor, adding a separating space only
    /// when the preceding character needs one — the Android commit law,
    /// expressed through iOS's native proxy.
    private func commit(_ transcript: String) {
        let before = textDocumentProxy.documentContextBeforeInput
        if let last = before?.last, !last.isWhitespace, !last.isNewline {
            textDocumentProxy.insertText(" ")
        }
        textDocumentProxy.insertText(transcript)
    }
}
