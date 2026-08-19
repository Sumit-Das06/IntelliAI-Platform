import AVFoundation
import SwiftUI

/// The IntelliAI container app: everything the keyboard extension must
/// NOT do itself — onboarding, API-key entry into the shared Keychain,
/// server address, language and contribution settings, the microphone
/// permission grant, and the correction editor. The extension only
/// READS what this app writes.
@main
struct IntelliAIApp: App {
    var body: some Scene {
        WindowGroup {
            SetupView()
        }
    }
}

struct SetupView: View {
    private let settings = SettingsStore()
    private let keychain = KeychainStore()

    @State private var apiKeyInput = ""
    @State private var maskedKey: String?
    @State private var serverAddress = ""
    @State private var language: DictationLanguage = .default
    @State private var contribute = true
    @State private var micGranted = WavRecorder.permissionGranted
    @State private var showingCorrection = false
    @State private var collected: (sampleId: String, transcript: String)?

    var body: some View {
        NavigationStack {
            Form {
                Section("1. Enable the keyboard") {
                    Text(
                        "Settings → General → Keyboard → Keyboards → "
                            + "Add New Keyboard → IntelliAI, then allow Full Access "
                            + "(needed to reach IntelliAI over the network)."
                    )
                    .font(.footnote)
                    Button("Open Settings") {
                        if let url = URL(string: UIApplication.openSettingsURLString) {
                            UIApplication.shared.open(url)
                        }
                    }
                }

                Section("2. API key") {
                    if let maskedKey {
                        LabeledContent("Saved key", value: maskedKey)
                        Button("Remove key", role: .destructive) {
                            keychain.delete()
                            self.maskedKey = nil
                        }
                    } else {
                        SecureField("ik_live_…", text: $apiKeyInput)
                            .textInputAutocapitalization(.never)
                            .autocorrectionDisabled()
                        Button("Save key") {
                            let trimmed = apiKeyInput.trimmingCharacters(
                                in: .whitespacesAndNewlines
                            )
                            guard !trimmed.isEmpty else { return }
                            keychain.write(trimmed)
                            maskedKey = KeychainStore.masked(trimmed)
                            apiKeyInput = ""
                        }
                    }
                }

                Section("3. Server") {
                    TextField("https://api.yourdomain.com", text: $serverAddress)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        .keyboardType(.URL)
                        .onSubmit { settings.serverAddress = serverAddress }
                    Button("Save server address") { settings.serverAddress = serverAddress }
                }

                Section("4. Microphone") {
                    if micGranted {
                        Label("Microphone allowed", systemImage: "checkmark.circle")
                    } else {
                        Button("Allow microphone") { requestMicrophone() }
                        Text(
                            "The keyboard cannot ask for this itself — grant it "
                                + "here once and dictation works everywhere."
                        )
                        .font(.footnote)
                    }
                }

                Section("Dictation") {
                    Picker("Language", selection: $language) {
                        ForEach(DictationLanguage.allCases, id: \.self) { choice in
                            Text(choice.displayName).tag(choice)
                        }
                    }
                    .onChange(of: language) { _, chosen in settings.language = chosen }

                    Toggle("Improve IntelliAI STT", isOn: $contribute)
                        .onChange(of: contribute) { _, on in settings.contribute = on }
                    Text(
                        "When on, your dictations may be stored to improve "
                            + "IntelliAI — only if your organization has consented. "
                            + "When off, nothing is stored."
                    )
                    .font(.footnote)
                }

                if let collected {
                    Section("Last dictation") {
                        Text(collected.transcript).font(.footnote).lineLimit(3)
                        Button("Improve this transcription") { showingCorrection = true }
                    }
                }
            }
            .navigationTitle("IntelliAI")
            .onAppear(perform: load)
            .sheet(isPresented: $showingCorrection) {
                if let collected {
                    CorrectionView(
                        sampleId: collected.sampleId,
                        originalTranscript: collected.transcript,
                        onDone: {
                            settings.clearCollected()
                            self.collected = nil
                            showingCorrection = false
                        }
                    )
                }
            }
        }
    }

    private func load() {
        if let key = keychain.read() { maskedKey = KeychainStore.masked(key) }
        serverAddress = settings.serverAddress
        language = settings.language
        contribute = settings.contribute
        collected = settings.lastCollected
        micGranted = WavRecorder.permissionGranted
    }

    private func requestMicrophone() {
        if #available(iOS 17.0, *) {
            AVAudioApplication.requestRecordPermission { granted in
                Task { @MainActor in micGranted = granted }
            }
        } else {
            AVAudioSession.sharedInstance().requestRecordPermission { granted in
                Task { @MainActor in micGranted = granted }
            }
        }
    }
}
