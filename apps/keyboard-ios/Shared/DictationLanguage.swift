import Foundation

/// The dictation languages the user can choose — the single canonical
/// mapping between a UI choice and what IntelliAI STT is told. Mirrors
/// the Android client and the public API contract exactly:
///
///     Auto    → apiTag nil → the `language` field is OMITTED (server detects)
///     English → "en"
///     Hindi   → "hi"
///     Arabic  → "ar"
///
/// Only these four values can ever reach the API — arbitrary language
/// strings never travel through the app.
enum DictationLanguage: String, CaseIterable, Codable {
    case auto
    case english = "en"
    case hindi = "hi"
    case arabic = "ar"

    static let `default`: DictationLanguage = .auto

    /// What goes into the request's `language` field; nil means omit.
    var apiTag: String? {
        self == .auto ? nil : rawValue
    }

    /// Compact keyboard chip label.
    var indicator: String {
        switch self {
        case .auto: return "Auto"
        case .english: return "EN"
        case .hindi: return "HI"
        case .arabic: return "AR"
        }
    }

    /// Human name for the settings screen.
    var displayName: String {
        switch self {
        case .auto: return "Auto-detect"
        case .english: return "English"
        case .hindi: return "हिन्दी (Hindi)"
        case .arabic: return "العربية (Arabic)"
        }
    }

    /// Resolve a persisted preference back to a choice; unknown or
    /// absent values fall back to Auto so a new install — or a
    /// corrupted value — is always Auto.
    static func fromPreference(_ value: String?) -> DictationLanguage {
        guard let value else { return .default }
        return DictationLanguage(rawValue: value) ?? .default
    }
}
