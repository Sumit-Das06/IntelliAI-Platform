import Foundation
import Security

/// The API key's ONLY home: the iOS Keychain, in a shared access group
/// so the container app (which sets the key) and the keyboard extension
/// (which uses it) read the same item — Apple's supported mechanism for
/// credential sharing between an app and its extensions.
///
/// The key is NEVER placed in UserDefaults, files, logs, the clipboard,
/// or keyboard shared text. After saving, the UI shows only the masked
/// form (`masked(_:)`). `kSecAttrAccessibleAfterFirstUnlock` keeps
/// dictation working after a reboot-then-unlock without exposing the
/// item before the first unlock; Keychain items are excluded from
/// unencrypted backups by construction.
struct KeychainStore {
    /// Must match the `keychain-access-groups` entitlement on BOTH
    /// targets. `$(AppIdentifierPrefix)` is prepended by the system.
    static let accessGroup = "com.intelliai.keyboard.shared"
    private static let service = "com.intelliai.keyboard.api-key"
    private static let account = "intelliai"

    private let useAccessGroup: Bool

    /// `useAccessGroup: false` exists for unit tests on the simulator,
    /// where access groups require provisioning.
    init(useAccessGroup: Bool = true) {
        self.useAccessGroup = useAccessGroup
    }

    // MARK: - CRUD

    @discardableResult
    func write(_ key: String) -> Bool {
        delete()
        var attributes = baseQuery()
        attributes[kSecValueData as String] = Data(key.utf8)
        attributes[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlock
        return SecItemAdd(attributes as CFDictionary, nil) == errSecSuccess
    }

    func read() -> String? {
        var query = baseQuery()
        query[kSecReturnData as String] = true
        query[kSecMatchLimit as String] = kSecMatchLimitOne
        var result: AnyObject?
        guard SecItemCopyMatching(query as CFDictionary, &result) == errSecSuccess,
              let data = result as? Data
        else { return nil }
        return String(data: data, encoding: .utf8)
    }

    @discardableResult
    func delete() -> Bool {
        let status = SecItemDelete(baseQuery() as CFDictionary)
        return status == errSecSuccess || status == errSecItemNotFound
    }

    /// Rotation = write: the previous item is deleted first, atomically
    /// from the caller's point of view.
    @discardableResult
    func rotate(to newKey: String) -> Bool {
        write(newKey)
    }

    private func baseQuery() -> [String: Any] {
        var query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: Self.service,
            kSecAttrAccount as String: Self.account,
        ]
        if useAccessGroup {
            query[kSecAttrAccessGroup as String] = Self.accessGroup
        }
        return query
    }

    // MARK: - Display

    /// The only form of the key any UI may show after saving: the
    /// public prefix plus the last four characters. Pure, unit-tested.
    static func masked(_ key: String) -> String {
        let trimmed = key.trimmingCharacters(in: .whitespacesAndNewlines)
        guard trimmed.count > 12 else { return String(repeating: "•", count: trimmed.count) }
        let prefix = trimmed.prefix(8)
        let suffix = trimmed.suffix(4)
        return "\(prefix)••••\(suffix)"
    }
}
