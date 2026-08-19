import Foundation

/// Non-secret settings shared between the container app and the
/// keyboard extension through the App Group — ONE source of truth,
/// exactly like Android's plain-preferences split:
///
/// - **Non-secret** (dictation language, server address, contribution
///   choice, last sample id) lives here, in App Group UserDefaults.
/// - **Secret** (the API key) NEVER enters UserDefaults — it lives in
///   the shared Keychain (`KeychainStore`).
///
/// The suite name must match the `com.apple.security.application-groups`
/// entitlement on BOTH targets.
struct SettingsStore {
    static let appGroup = "group.com.intelliai.keyboard"

    private enum Keys {
        static let language = "dictation_language"
        static let serverAddress = "server_address"
        static let contribute = "contribute"
        static let lastSampleId = "last_sample_id"
        static let lastTranscript = "last_transcript"
    }

    private let defaults: UserDefaults

    /// The production entry point; falls back to standard defaults only
    /// if the App Group is unavailable (misprovisioned build) so the
    /// keyboard still functions rather than crashing.
    init(defaults: UserDefaults? = nil) {
        self.defaults = defaults ?? UserDefaults(suiteName: Self.appGroup) ?? .standard
    }

    // MARK: - Language (Auto by default, always resolvable)

    var language: DictationLanguage {
        get { DictationLanguage.fromPreference(defaults.string(forKey: Keys.language)) }
        nonmutating set { defaults.set(newValue.rawValue, forKey: Keys.language) }
    }

    // MARK: - Server address (non-secret; validated at request time)

    var serverAddress: String {
        get { defaults.string(forKey: Keys.serverAddress) ?? "" }
        nonmutating set {
            defaults.set(
                newValue.trimmingCharacters(in: .whitespacesAndNewlines),
                forKey: Keys.serverAddress
            )
        }
    }

    // MARK: - Contribution (ON by default; server consent is the ceiling)

    var contribute: Bool {
        get { defaults.object(forKey: Keys.contribute) as? Bool ?? true }
        nonmutating set { defaults.set(newValue, forKey: Keys.contribute) }
    }

    // MARK: - Correction handoff (keyboard → container app)

    /// The keyboard records the last collected sample so the container
    /// app can offer "Improve this transcription". Only the id and the
    /// returned transcript travel — never audio, never the API key.
    func recordCollected(sampleId: String, transcript: String) {
        defaults.set(sampleId, forKey: Keys.lastSampleId)
        defaults.set(transcript, forKey: Keys.lastTranscript)
    }

    var lastCollected: (sampleId: String, transcript: String)? {
        guard let id = defaults.string(forKey: Keys.lastSampleId), !id.isEmpty,
              let text = defaults.string(forKey: Keys.lastTranscript)
        else { return nil }
        return (id, text)
    }

    func clearCollected() {
        defaults.removeObject(forKey: Keys.lastSampleId)
        defaults.removeObject(forKey: Keys.lastTranscript)
    }
}
