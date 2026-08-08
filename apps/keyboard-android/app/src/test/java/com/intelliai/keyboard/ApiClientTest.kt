package com.intelliai.keyboard

import com.intelliai.keyboard.api.ApiOutcome
import com.intelliai.keyboard.api.FailureKind
import com.intelliai.keyboard.api.IntelliAIApiClient
import okhttp3.OkHttpClient
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import java.util.concurrent.TimeUnit

/**
 * The keyboard ↔ IntelliAI wire contract, pinned against a mock server.
 * These tests assert the REAL platform contract (multipart fields,
 * headers, the error envelope's type/code semantics) — they are the
 * executable copy of the backend inspection, not a parallel invention.
 */
class ApiClientTest {

    private val server = MockWebServer()
    private val testKey = "ik_live_" + "A".repeat(43)
    private lateinit var client: IntelliAIApiClient

    @Before
    fun setUp() {
        server.start()
        client = IntelliAIApiClient(
            baseUrl = { server.url("/").toString() },
            apiKey = { testKey },
        )
    }

    @After
    fun tearDown() {
        server.shutdown()
    }

    private fun enqueue(code: Int, body: String, vararg headers: Pair<String, String>) {
        val response = MockResponse().setResponseCode(code).setBody(body)
        headers.forEach { (name, value) -> response.addHeader(name, value) }
        server.enqueue(response)
    }

    private fun envelope(type: String, code: String? = null, message: String = "msg"): String =
        """{"error":{"type":"$type","code":${code?.let { "\"$it\"" } ?: "null"},"message":"$message","param":null,"request_id":"req_x"}}"""

    // ── Request formation ───────────────────────────────────────────

    @Test
    fun `request is a multipart POST to the transcriptions endpoint with both headers`() {
        enqueue(200, """{"text":"hi"}""")
        client.transcribe(byteArrayOf(1, 2, 3))

        val request = server.takeRequest()
        assertEquals("POST", request.method)
        assertEquals("/v1/audio/transcriptions", request.path)
        assertEquals("Bearer $testKey", request.getHeader("Authorization"))
        assertEquals("keyboard/1.0", request.getHeader("X-IntelliAI-Client"))
        assertTrue(request.getHeader("Content-Type")!!.startsWith("multipart/form-data"))

        val body = request.body.readUtf8()
        assertTrue(body.contains("name=\"model\""))
        assertTrue(body.contains("intelliai-stt"))
        assertTrue(body.contains("name=\"file\""))
        assertTrue(body.contains("filename=\"dictation.wav\""))
        assertTrue(body.contains("Content-Type: audio/wav"))
    }

    @Test
    fun `auto language omits the language field entirely`() {
        enqueue(200, """{"text":"hi"}""")
        client.transcribe(byteArrayOf(1), language = null)
        assertFalse(server.takeRequest().body.readUtf8().contains("name=\"language\""))
    }

    @Test
    fun `each explicit language is sent as its own form field value`() {
        for (tag in listOf("en", "hi", "ar")) {
            enqueue(200, """{"text":"ok"}""")
            client.transcribe(byteArrayOf(1), language = tag)
            val body = server.takeRequest().body.readUtf8()
            assertTrue("missing language field for $tag", body.contains("name=\"language\""))
            // The value sits on its own line in the multipart part body.
            assertTrue("wrong value for $tag", body.contains("\r\n\r\n$tag\r\n"))
        }
    }

    @Test
    fun `no prompt or temperature fields exist`() {
        enqueue(200, """{"text":"hi"}""")
        client.transcribe(byteArrayOf(1))
        val body = server.takeRequest().body.readUtf8()
        assertFalse(body.contains("name=\"prompt\""))
        assertFalse(body.contains("name=\"temperature\""))
    }

    // ── Success handling ────────────────────────────────────────────

    @Test
    fun `success parses text and the sample header`() {
        enqueue(200, """{"text":"hello world"}""", "X-IntelliAI-Sample" to "smp_abc")
        val outcome = client.transcribe(byteArrayOf(1)) as ApiOutcome.Success
        assertEquals("hello world", outcome.text)
        assertEquals("smp_abc", outcome.sampleId)
    }

    @Test
    fun `success without the sample header carries no sample id`() {
        enqueue(200, """{"text":"hello"}""")
        assertNull((client.transcribe(byteArrayOf(1)) as ApiOutcome.Success).sampleId)
    }

    @Test
    fun `blank transcript is NO_SPEECH, never inserted text`() {
        enqueue(200, """{"text":""}""")
        val outcome = client.transcribe(byteArrayOf(1)) as ApiOutcome.Failure
        assertEquals(FailureKind.NO_SPEECH, outcome.kind)
    }

    // ── Error envelope semantics ────────────────────────────────────

    @Test
    fun `invalid revoked and expired keys are all BAD_API_KEY`() {
        for (code in listOf("invalid_api_key", "api_key_revoked", "api_key_expired")) {
            enqueue(401, envelope("authentication_error", code))
            val outcome = client.transcribe(byteArrayOf(1)) as ApiOutcome.Failure
            assertEquals(code, FailureKind.BAD_API_KEY, outcome.kind)
        }
    }

    @Test
    fun `missing key per the server is NO_API_KEY`() {
        enqueue(401, envelope("authentication_error", "missing_api_key"))
        assertEquals(
            FailureKind.NO_API_KEY,
            (client.transcribe(byteArrayOf(1)) as ApiOutcome.Failure).kind,
        )
    }

    @Test
    fun `quota 429 is QUOTA - not rate limiting - and is not retried`() {
        // The platform's sharpest client trap: same status, opposite
        // meaning, distinguished ONLY by error.type; no Retry-After.
        enqueue(429, envelope("quota_exceeded_error", "quota_exceeded"))
        val outcome = client.transcribe(byteArrayOf(1)) as ApiOutcome.Failure
        assertEquals(FailureKind.QUOTA, outcome.kind)
        assertNull(outcome.retryAfterSeconds)
        assertEquals(1, server.requestCount) // exactly one attempt
    }

    @Test
    fun `rate limit 429 is RATE_LIMITED with the retry hint`() {
        enqueue(429, envelope("rate_limit_error", "rate_limit_exceeded"), "Retry-After" to "7")
        val outcome = client.transcribe(byteArrayOf(1)) as ApiOutcome.Failure
        assertEquals(FailureKind.RATE_LIMITED, outcome.kind)
        assertEquals(7, outcome.retryAfterSeconds)
        assertEquals(1, server.requestCount) // the CLIENT does not auto-retry rate limits
    }

    @Test
    fun `503 gets exactly one bounded retry and can succeed`() {
        enqueue(503, envelope("service_unavailable_error", "model_loading"), "Retry-After" to "1")
        enqueue(200, """{"text":"after warmup"}""")
        val outcome = client.transcribe(byteArrayOf(1)) as ApiOutcome.Success
        assertEquals("after warmup", outcome.text)
        assertEquals(2, server.requestCount)
    }

    @Test
    fun `503 twice surfaces UNAVAILABLE after the single retry`() {
        enqueue(503, envelope("service_unavailable_error", "overloaded"), "Retry-After" to "1")
        enqueue(503, envelope("service_unavailable_error", "overloaded"), "Retry-After" to "1")
        val outcome = client.transcribe(byteArrayOf(1)) as ApiOutcome.Failure
        assertEquals(FailureKind.UNAVAILABLE, outcome.kind)
        assertEquals(2, server.requestCount) // one retry, never a storm
    }

    @Test
    fun `validation errors surface the server's human message`() {
        enqueue(
            400,
            envelope("invalid_request_error", "language_not_supported", "Language 'xx' is not served."),
        )
        val outcome = client.transcribe(byteArrayOf(1)) as ApiOutcome.Failure
        assertEquals(FailureKind.REJECTED, outcome.kind)
        assertEquals("Language 'xx' is not served.", outcome.serverMessage)
    }

    @Test
    fun `malformed error bodies fall back to status semantics safely`() {
        enqueue(500, "<html>gateway exploded</html>")
        assertEquals(
            FailureKind.SERVER,
            (client.transcribe(byteArrayOf(1)) as ApiOutcome.Failure).kind,
        )
        enqueue(401, "not json either")
        assertEquals(
            FailureKind.BAD_API_KEY,
            (client.transcribe(byteArrayOf(1)) as ApiOutcome.Failure).kind,
        )
    }

    @Test
    fun `network timeout is NETWORK, not a crash`() {
        val impatient = IntelliAIApiClient(
            baseUrl = { server.url("/").toString() },
            apiKey = { testKey },
            client = OkHttpClient.Builder()
                .callTimeout(300, TimeUnit.MILLISECONDS)
                .build(),
        )
        server.enqueue(MockResponse().setHeadersDelay(2, TimeUnit.SECONDS))
        assertEquals(
            FailureKind.NETWORK,
            (impatient.transcribe(byteArrayOf(1)) as ApiOutcome.Failure).kind,
        )
    }

    @Test
    fun `missing key client-side never touches the network`() {
        val keyless = IntelliAIApiClient(baseUrl = { server.url("/").toString() }, apiKey = { null })
        assertEquals(
            FailureKind.NO_API_KEY,
            (keyless.transcribe(byteArrayOf(1)) as ApiOutcome.Failure).kind,
        )
        assertEquals(0, server.requestCount)
    }

    // ── Secret hygiene ──────────────────────────────────────────────

    @Test
    fun `the api key never appears in any outcome`() {
        for (response in listOf(
            Triple(401, envelope("authentication_error", "invalid_api_key"), null),
            Triple(429, envelope("quota_exceeded_error", "quota_exceeded"), null),
            Triple(500, "boom", null),
        )) {
            enqueue(response.first, response.second)
            val outcome = client.transcribe(byteArrayOf(1))
            val rendered = outcome.toString()
            assertFalse("key leaked into $rendered", rendered.contains(testKey))
            assertFalse(rendered.contains("A".repeat(20)))
        }
    }
}
