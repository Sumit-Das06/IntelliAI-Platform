package com.intelliai.keyboard.settings

/**
 * The one rule for what counts as a usable IntelliAI server address,
 * shared by the settings screen (rejecting bad input at save time) and
 * the API client (refusing to send a request to one that slipped
 * through anyway — old prefs, restored data). Pure and JVM-testable.
 *
 * Debug builds may talk cleartext to the emulator's host loopback —
 * that is what debug is for. Release builds accept HTTPS only, and
 * never a development host: a production keyboard pointed at
 * 10.0.2.2 or localhost is a misconfiguration, not a server.
 */
object ServerAddress {

    enum class Verdict {
        OK,

        /** Not http(s):// at all — unusable in any build. */
        MALFORMED,

        /** Cleartext or a development host in a release build. */
        RELEASE_UNSAFE,
    }

    /** Hosts that can only ever mean "a developer's own machine". */
    private val DEV_HOSTS = setOf("10.0.2.2", "localhost", "127.0.0.1", "[::1]")

    fun validate(url: String, debugBuild: Boolean): Verdict {
        val trimmed = url.trim()
        val isHttps = trimmed.startsWith("https://")
        val isHttp = trimmed.startsWith("http://")
        if (!isHttp && !isHttps) return Verdict.MALFORMED
        if (debugBuild) return Verdict.OK
        if (isHttp) return Verdict.RELEASE_UNSAFE
        val host = trimmed.removePrefix("https://")
            .substringBefore('/')
            .substringBefore('?')
            .let { authority ->
                // Strip a port, but not the colons inside an IPv6 literal.
                if (authority.startsWith("[")) authority.substringBefore(']') + "]"
                else authority.substringBefore(':')
            }
            .lowercase()
        if (host in DEV_HOSTS) return Verdict.RELEASE_UNSAFE
        return Verdict.OK
    }
}
