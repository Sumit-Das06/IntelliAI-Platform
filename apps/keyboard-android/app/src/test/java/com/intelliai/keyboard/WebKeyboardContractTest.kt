package com.intelliai.keyboard

import com.intelliai.keyboard.api.ApiOutcome
import com.intelliai.keyboard.api.FailureKind
import com.intelliai.keyboard.api.IntelliAIApiClient
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import okhttp3.mockwebserver.SocketPolicy
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/**
 * THE ARCHITECTURE PIN: the Android keyboard and the Web STT Studio are
 * two clients of the SAME IntelliAI backend — one endpoint, one model
 * id, one auth scheme, one language semantic, one error envelope, one
 * correction flow. There is no Android STT path and there must never
 * be one.
 *
 * Each assertion here is the keyboard half of a contract whose web half
 * lives in the platform (apps/api/src/intelliai_api/static/console/
 * studio.html and api/v1/audio/transcriptions.py). If a change breaks
 * one of these, the fix is to keep the clients identical — never to
 * fork the pipeline. The ONLY intended differences between the clients
 * are provenance (X-IntelliAI-Client), UX, and audio capture.
 */
class WebKeyboardContractTest {

    private val server = MockWebServer()
    private lateinit var client: IntelliAIApiClient

    @Before
    fun setUp() {
        server.start()
        client = IntelliAIApiClient(
            baseUrl = { server.url("/").toString() },
            apiKey = { "ik_live_" + "A".repeat(43) },
            debugBuild = true,
        )
    }

    @After
    fun tearDown() {
        server.shutdown()
    }

    // ── One endpoint, one model, one auth scheme ────────────────────

    @Test
    fun `transcription hits the exact path and model id the web studio uses`() {
        server.enqueue(MockResponse().setBody("""{"text":"hello"}"""))
        client.transcribe(byteArrayOf(1))
        val request = server.takeRequest()
        // studio.html: fetch("/v1/audio/transcriptions") + form.append("model", "intelliai-stt")
        assertEquals("/v1/audio/transcriptions", request.path)
        val body = request.body.readUtf8()
        assertTrue(body.contains("name=\"model\""))
        assertTrue(body.contains("intelliai-stt"))
        // Same auth scheme as the web: a Console API key as a Bearer token.
        assertTrue(request.getHeader("Authorization")!!.startsWith("Bearer ik_live_"))
    }

    @Test
    fun `provenance is the ONLY identity difference - keyboard slash 1 dot 0`() {
        server.enqueue(MockResponse().setBody("""{"text":"hello"}"""))
        client.transcribe(byteArrayOf(1))
        // studio.html sends "web"; the keyboard sends "keyboard/1.0".
        // Same header, different value — that is the entire difference.
        assertEquals("keyboard/1.0", server.takeRequest().getHeader("X-IntelliAI-Client"))
    }

    @Test
    fun `correction hits the exact sample endpoint and body shape the web studio uses`() {
        server.enqueue(
            MockResponse().setBody(
                """{"id":"smp_1","corrected_text":"fixed","last_modified_at":"2026-08-09T00:00:00Z"}"""
            )
        )
        client.correct("smp_1", "fixed")
        val request = server.takeRequest()
        // studio.html: apiJSON("/v1/audio/transcriptions/" + sampleId + "/correction")
        assertEquals("/v1/audio/transcriptions/smp_1/correction", request.path)
        assertEquals("""{"corrected_text":"fixed"}""", request.body.readUtf8())
    }

    // ── One language semantic ───────────────────────────────────────

    @Test
    fun `auto omits language exactly as the web studio's empty selection does`() {
        server.enqueue(MockResponse().setBody("""{"text":"x"}"""))
        client.transcribe(byteArrayOf(1), language = null)
        // studio.html: if (langSelect.value) form.append("language", …) —
        // no value, no field. The keyboard's Auto is the same absence.
        assertFalse(server.takeRequest().body.readUtf8().contains("name=\"language\""))
    }

    @Test
    fun `explicit languages are the same two-letter tags the platform serves`() {
        for (tag in listOf("en", "hi", "ar")) {
            server.enqueue(MockResponse().setBody("""{"text":"x"}"""))
            client.transcribe(byteArrayOf(1), language = tag)
            val body = server.takeRequest().body.readUtf8()
            assertTrue("language=$tag must be a form field", body.contains("name=\"language\""))
            assertTrue(body.contains(tag))
        }
    }

    // ── One error envelope ──────────────────────────────────────────

    @Test
    fun `the keyboard branches on the envelope's type - never on raw status`() {
        // Both 429s below share a status code; the envelope's type is
        // what separates "stop, you're out of quota" from "slow down" —
        // for the web console and the keyboard alike.
        server.enqueue(
            MockResponse().setResponseCode(429).setBody(
                """{"error":{"type":"quota_exceeded_error","code":"quota_exceeded","message":"m","param":null,"request_id":"r"}}"""
            )
        )
        val quota = client.transcribe(byteArrayOf(1)) as ApiOutcome.Failure
        assertEquals(FailureKind.QUOTA, quota.kind)

        server.enqueue(
            MockResponse().setResponseCode(429).addHeader("Retry-After", "7").setBody(
                """{"error":{"type":"rate_limit_error","code":"rate_limited","message":"m","param":null,"request_id":"r"}}"""
            )
        )
        val rate = client.transcribe(byteArrayOf(1)) as ApiOutcome.Failure
        assertEquals(FailureKind.RATE_LIMITED, rate.kind)
        assertEquals(7, rate.retryAfterSeconds)
    }

    // ── One collection signal ───────────────────────────────────────

    @Test
    fun `collection is announced only by the platform's sample header`() {
        // The keyboard never decides collection client-side: the
        // X-IntelliAI-Sample header (set only when the backend actually
        // stored a consented sample) is the sole signal — the same one
        // the web studio uses to offer its correction UI.
        server.enqueue(
            MockResponse().setBody("""{"text":"x"}""").addHeader("X-IntelliAI-Sample", "smp_9")
        )
        val collected = client.transcribe(byteArrayOf(1)) as ApiOutcome.Success
        assertEquals("smp_9", collected.sampleId)

        server.enqueue(MockResponse().setBody("""{"text":"x"}"""))
        val notCollected = client.transcribe(byteArrayOf(1)) as ApiOutcome.Success
        assertEquals(null, notCollected.sampleId)
    }

    // ── Reliability edges a phone actually meets ────────────────────

    @Test
    fun `connection cut mid-upload is NETWORK - the keyboard returns to usable`() {
        server.enqueue(
            MockResponse().setSocketPolicy(SocketPolicy.DISCONNECT_DURING_REQUEST_BODY)
        )
        val outcome = client.transcribe(ByteArray(100_000)) as ApiOutcome.Failure
        assertEquals(FailureKind.NETWORK, outcome.kind)
    }

    @Test
    fun `a 200 with a non-JSON body is NO_SPEECH - never a crash, never garbage text`() {
        server.enqueue(MockResponse().setBody("<html>proxy interfered</html>"))
        val outcome = client.transcribe(byteArrayOf(1)) as ApiOutcome.Failure
        assertEquals(FailureKind.NO_SPEECH, outcome.kind)
    }

    @Test
    fun `server 503 variants all land on UNAVAILABLE with bounded retry`() {
        // model_loading, overloaded, runtime_unavailable — one family,
        // one client behavior: a single bounded retry, then honesty.
        for (code in listOf("model_loading", "overloaded", "runtime_unavailable")) {
            server.enqueue(
                MockResponse().setResponseCode(503).addHeader("Retry-After", "1").setBody(
                    """{"error":{"type":"service_unavailable_error","code":"$code","message":"m","param":null,"request_id":"r"}}"""
                )
            )
            server.enqueue(
                MockResponse().setResponseCode(503).addHeader("Retry-After", "1").setBody(
                    """{"error":{"type":"service_unavailable_error","code":"$code","message":"m","param":null,"request_id":"r"}}"""
                )
            )
            val outcome = client.transcribe(byteArrayOf(1)) as ApiOutcome.Failure
            assertEquals(code, FailureKind.UNAVAILABLE, outcome.kind)
        }
    }
}
