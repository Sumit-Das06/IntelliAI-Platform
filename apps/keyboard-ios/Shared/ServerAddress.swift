import Foundation

/// Server-address validation, mirroring the Android client's law:
/// release builds speak HTTPS to real hosts and NOTHING else; debug
/// builds may additionally reach local development hosts. The check
/// runs before every request (defense in depth behind the settings
/// screen and App Transport Security) so a misconfigured address
/// produces an HONEST error instead of an opaque connection failure.
enum ServerAddress {
    enum Verdict {
        case ok
        case malformed
        case releaseUnsafe
    }

    /// Hosts a DEBUG build may reach over any scheme: the developer's
    /// own machine (simulator loopback) — same set as Android's debug
    /// network-security config.
    private static let debugHosts: Set<String> = ["localhost", "127.0.0.1", "10.0.2.2"]

    static func validate(_ address: String, debugBuild: Bool) -> Verdict {
        let trimmed = address.trimmingCharacters(in: .whitespacesAndNewlines)
        guard let url = URL(string: trimmed),
              let scheme = url.scheme?.lowercased(),
              let host = url.host,
              !host.isEmpty,
              scheme == "https" || scheme == "http"
        else {
            return .malformed
        }
        if scheme == "https" { return .ok }
        // http:// — permissible only in debug, only to development hosts.
        if debugBuild, debugHosts.contains(host.lowercased()) { return .ok }
        return .releaseUnsafe
    }
}
