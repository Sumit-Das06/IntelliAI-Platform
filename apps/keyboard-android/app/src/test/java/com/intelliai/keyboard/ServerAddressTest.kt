package com.intelliai.keyboard

import com.intelliai.keyboard.settings.ServerAddress
import com.intelliai.keyboard.settings.ServerAddress.Verdict
import org.junit.Assert.assertEquals
import org.junit.Test

/**
 * The one rule for a usable IntelliAI server address, as a matrix.
 * Debug is for developers (any http(s) address, including the emulator
 * loopback); release accepts only HTTPS to a real host.
 */
class ServerAddressTest {

    private fun verdict(url: String, debug: Boolean): Verdict =
        ServerAddress.validate(url, debugBuild = debug)

    // ── Both builds ─────────────────────────────────────────────────

    @Test
    fun `not http or https at all is malformed in any build`() {
        for (bad in listOf("", "   ", "ftp://x", "server.example.com", "https:/oops", "file:///etc")) {
            assertEquals(bad, Verdict.MALFORMED, verdict(bad, debug = true))
            assertEquals(bad, Verdict.MALFORMED, verdict(bad, debug = false))
        }
    }

    @Test
    fun `a real https address is fine everywhere`() {
        for (ok in listOf(
            "https://api.intelliai.example",
            "https://api.intelliai.example:8443",
            "https://api.intelliai.example/v1",
            "  https://api.intelliai.example  ",
        )) {
            assertEquals(ok, Verdict.OK, verdict(ok, debug = true))
            assertEquals(ok, Verdict.OK, verdict(ok, debug = false))
        }
    }

    // ── Debug: the developer loopback is the point ──────────────────

    @Test
    fun `debug accepts cleartext to the emulator loopback`() {
        assertEquals(Verdict.OK, verdict("http://10.0.2.2:8000", debug = true))
        assertEquals(Verdict.OK, verdict("http://localhost:8000", debug = true))
    }

    // ── Release: HTTPS only, and never a development host ───────────

    @Test
    fun `release refuses every cleartext address`() {
        for (bad in listOf(
            "http://10.0.2.2:8000",
            "http://api.intelliai.example",
            "http://localhost",
        )) {
            assertEquals(bad, Verdict.RELEASE_UNSAFE, verdict(bad, debug = false))
        }
    }

    @Test
    fun `release refuses development hosts even over https`() {
        for (bad in listOf(
            "https://10.0.2.2:8443",
            "https://localhost",
            "https://LOCALHOST:9443/path",
            "https://127.0.0.1",
            "https://[::1]:8443",
        )) {
            assertEquals(bad, Verdict.RELEASE_UNSAFE, verdict(bad, debug = false))
        }
    }

    @Test
    fun `a host merely containing a dev-host string is not punished`() {
        // "localhost.intelliai.example" is a real (odd) host, not the
        // loopback — exact-host matching, not substring paranoia.
        assertEquals(Verdict.OK, verdict("https://localhost.intelliai.example", debug = false))
        assertEquals(Verdict.OK, verdict("https://my10.0.2.2ish.example", debug = false))
    }
}
