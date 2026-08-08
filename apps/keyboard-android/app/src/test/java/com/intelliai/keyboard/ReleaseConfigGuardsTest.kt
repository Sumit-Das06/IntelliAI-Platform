package com.intelliai.keyboard

import com.intelliai.keyboard.api.ApiOutcome
import com.intelliai.keyboard.api.CorrectionOutcome
import com.intelliai.keyboard.api.FailureKind
import com.intelliai.keyboard.api.IntelliAIApiClient
import okhttp3.mockwebserver.MockWebServer
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/**
 * 13E release-configuration guards. These run for EVERY build variant
 * (`gradlew test` executes debug and release unit tests), so the
 * BuildConfig-conditional assertions genuinely check the RELEASE
 * configuration in CI — a development default or cleartext endpoint in
 * a release build is a red build, not a code review hope.
 */
class ReleaseConfigGuardsTest {

    // ── The compiled-in default server address ──────────────────────

    @Test
    fun `release ships no development default - debug ships exactly the emulator loopback`() {
        if (BuildConfig.DEBUG) {
            // Debug's default is the emulator's host loopback and
            // nothing else — a change here is a deliberate decision.
            assertEquals("http://10.0.2.2:8000", BuildConfig.DEFAULT_BASE_URL)
        } else {
            // Release ships NO default (the server is a deliberate
            // configuration) — and could only ever ship an https one.
            val default = BuildConfig.DEFAULT_BASE_URL
            assertTrue(
                "release default must be empty or https://, was '$default'",
                default.isEmpty() || default.startsWith("https://"),
            )
            for (devHost in listOf("10.0.2.2", "localhost", "127.0.0.1")) {
                assertFalse(
                    "release default must never name a development host",
                    default.contains(devHost),
                )
            }
        }
    }

    @Test
    fun `version identity is real - never a hardcoded string`() {
        // The About line renders BuildConfig.VERSION_NAME; these pin
        // that the build actually carries a sane version to render.
        assertTrue(BuildConfig.VERSION_NAME.matches(Regex("""\d+(\.\d+)*""")))
        assertTrue(BuildConfig.VERSION_CODE >= 2)
        // And no source or resource may hardcode a display version that
        // can drift from Gradle's truth.
        val offenders = File("src/main").walkTopDown()
            .filter { it.isFile && it.extension in setOf("kt", "xml") }
            .filter { it.readText().contains(Regex("""Keyboard v\d""")) }
            .map { it.name }
            .toList()
        assertEquals(emptyList<String>(), offenders)
    }

    // ── The client refuses release-unsafe addresses outright ────────

    @Test
    fun `a release-mode client refuses cleartext before touching the network`() {
        val server = MockWebServer()
        server.start()
        try {
            val releaseLike = IntelliAIApiClient(
                baseUrl = { server.url("/").toString() }, // http://localhost:…
                apiKey = { "ik_live_" + "A".repeat(43) },
                debugBuild = false,
            )
            val transcription = releaseLike.transcribe(byteArrayOf(1)) as ApiOutcome.Failure
            assertEquals(FailureKind.HTTPS_REQUIRED, transcription.kind)
            val correction = releaseLike.correct("smp_x", "text") as CorrectionOutcome.Failure
            assertEquals(FailureKind.HTTPS_REQUIRED, correction.kind)
            assertEquals("no request may leave the device", 0, server.requestCount)
        } finally {
            server.shutdown()
        }
    }

    @Test
    fun `a release-mode client refuses a development host even over https`() {
        val releaseLike = IntelliAIApiClient(
            baseUrl = { "https://10.0.2.2:8443" },
            apiKey = { "ik_live_" + "A".repeat(43) },
            debugBuild = false,
        )
        val outcome = releaseLike.transcribe(byteArrayOf(1)) as ApiOutcome.Failure
        assertEquals(FailureKind.HTTPS_REQUIRED, outcome.kind)
    }

    @Test
    fun `a garbage address is NO_BASE_URL - ask for configuration, not a crash`() {
        val client = IntelliAIApiClient(
            baseUrl = { "not-a-server" },
            apiKey = { "ik_live_" + "A".repeat(43) },
            debugBuild = false,
        )
        val outcome = client.transcribe(byteArrayOf(1)) as ApiOutcome.Failure
        assertEquals(FailureKind.NO_BASE_URL, outcome.kind)
    }

    // ── Secrets stay out of git ─────────────────────────────────────

    @Test
    fun `git ignores signing material and local sdk config`() {
        // Tests run with the app module as the working directory; the
        // repository root is three levels up (app → keyboard-android →
        // apps → root).
        val gitignore = File("../../../.gitignore").readText()
        for (required in listOf("*.jks", "*.keystore", "keystore.properties", "local.properties")) {
            assertTrue("$required must be gitignored", gitignore.contains(required))
        }
    }

    @Test
    fun `no keystore or key file is tracked anywhere in the app`() {
        val offenders = File(".").walkTopDown()
            .onEnter { it.name != "build" && it.name != ".gradle" }
            .filter { it.isFile && (it.extension == "jks" || it.extension == "keystore") }
            .map { it.path }
            .toList()
        assertEquals(emptyList<String>(), offenders)
    }
}
