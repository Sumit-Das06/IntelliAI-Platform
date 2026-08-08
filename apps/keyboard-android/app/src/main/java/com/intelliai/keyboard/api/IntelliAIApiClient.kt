package com.intelliai.keyboard.api

import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.io.IOException
import java.util.concurrent.TimeUnit

/**
 * The keyboard's one network capability: POST /v1/audio/transcriptions
 * against the IntelliAI platform. Thin by design — multipart request,
 * envelope-aware response handling, nothing else. The platform's error
 * contract branches on `error.type`/`error.code`, NEVER on HTTP status
 * alone: a quota 429 (no Retry-After, retrying never helps) and a
 * rate-limit 429 (Retry-After, backoff helps) share a status code and
 * mean opposite things.
 *
 * Privacy: the API key lives in the Authorization header and nowhere
 * else — never in logs, never in [ApiOutcome] messages, never in
 * exceptions. Audio bytes go into the request body and are not retained
 * by this class.
 */
class IntelliAIApiClient(
    private val baseUrl: () -> String,
    private val apiKey: () -> String?,
    client: OkHttpClient? = null,
) {

    // Timeouts sized for dictation against a CPU inference backend:
    // connect fails fast (10 s — unreachable is unreachable), the write
    // ships up to ~2 MB of WAV on slow links (30 s), and the read must
    // outlast the gateway's own 120 s runtime deadline so the SERVER
    // decides timeouts, not the phone. The overall call cap bounds the
    // worst case — nothing hangs forever.
    private val http: OkHttpClient = client ?: OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .writeTimeout(30, TimeUnit.SECONDS)
        .readTimeout(120, TimeUnit.SECONDS)
        .callTimeout(150, TimeUnit.SECONDS)
        .build()

    /**
     * Transcribe one WAV utterance. `language = null` means Auto: the
     * field is OMITTED entirely and the server detects the language.
     * (13C's selector will pass "en"/"hi"/"ar" here — same client, no
     * rewrite.) Blocking; callers dispatch off the main thread.
     */
    fun transcribe(
        wav: ByteArray,
        language: String? = null,
        contribute: Boolean = true,
    ): ApiOutcome {
        val key = apiKey()?.takeIf { it.isNotBlank() }
            ?: return ApiOutcome.Failure(FailureKind.NO_API_KEY)
        val base = baseUrl().trim().trimEnd('/')
        if (base.isEmpty()) return ApiOutcome.Failure(FailureKind.NO_BASE_URL)

        val body = MultipartBody.Builder()
            .setType(MultipartBody.FORM)
            .addFormDataPart("model", "intelliai-stt")
            .addFormDataPart(
                "file",
                "dictation.wav",
                wav.toRequestBody("audio/wav".toMediaType()),
            )
            .apply { language?.let { addFormDataPart("language", it) } }
            .build()
        val request = Request.Builder()
            .url("$base/v1/audio/transcriptions")
            .header("Authorization", "Bearer $key")
            .header("X-IntelliAI-Client", "keyboard/1.0")
            // Opt out ONLY when contribution is off. Sending nothing when
            // on preserves the server's existing behavior (and never
            // widens collection beyond org consent).
            .apply { if (!contribute) header("X-IntelliAI-Contribution", "off") }
            .post(body)
            .build()

        val first = executeSafely(request)
        // One bounded retry, only for the explicitly retryable 503
        // family (model_loading on a cold dev stack is the common case,
        // Retry-After: 2). Never more than one; never for anything else.
        if (first is ApiOutcome.Failure && first.kind == FailureKind.UNAVAILABLE) {
            val waitSeconds = (first.retryAfterSeconds ?: 1).coerceIn(1, 5)
            try {
                Thread.sleep(waitSeconds * 1000L)
            } catch (_: InterruptedException) {
                Thread.currentThread().interrupt()
                return first
            }
            return executeSafely(request)
        }
        return first
    }

    private fun executeSafely(request: Request): ApiOutcome = try {
        http.newCall(request).execute().use { response -> interpret(response.code, response) }
    } catch (_: IOException) {
        // Timeout, DNS, refused, offline — one honest bucket. The
        // exception text is deliberately dropped: raw socket messages
        // help nobody and can echo URLs.
        ApiOutcome.Failure(FailureKind.NETWORK)
    }

    private fun interpret(status: Int, response: okhttp3.Response): ApiOutcome {
        val bodyText = response.body?.string().orEmpty()
        if (status in 200..299) {
            val text = runCatching { JSONObject(bodyText).optString("text") }.getOrNull()
            if (text.isNullOrBlank()) return ApiOutcome.Failure(FailureKind.NO_SPEECH)
            return ApiOutcome.Success(
                text = text,
                sampleId = response.header("X-IntelliAI-Sample"),
            )
        }

        val error = runCatching { JSONObject(bodyText).getJSONObject("error") }.getOrNull()
        val type = error?.optString("type").orEmpty()
        val code = error?.optString("code").orEmpty()
        val serverMessage = error?.optString("message").orEmpty()
        val retryAfter = response.header("Retry-After")?.toIntOrNull()

        // error.type is the contract; status is only the fallback for
        // envelopes we cannot parse.
        return when {
            type == "authentication_error" -> ApiOutcome.Failure(
                if (code == "missing_api_key") FailureKind.NO_API_KEY else FailureKind.BAD_API_KEY
            )
            type == "quota_exceeded_error" -> ApiOutcome.Failure(FailureKind.QUOTA)
            type == "rate_limit_error" ->
                ApiOutcome.Failure(FailureKind.RATE_LIMITED, retryAfterSeconds = retryAfter)
            type == "service_unavailable_error" ->
                ApiOutcome.Failure(FailureKind.UNAVAILABLE, retryAfterSeconds = retryAfter)
            type == "invalid_request_error" || type == "resource_not_found_error" ->
                // The platform writes these messages for humans and they
                // carry no secrets — surface them (e.g. which languages
                // are served).
                ApiOutcome.Failure(FailureKind.REJECTED, serverMessage = serverMessage)
            status == 401 -> ApiOutcome.Failure(FailureKind.BAD_API_KEY)
            status == 429 -> ApiOutcome.Failure(FailureKind.RATE_LIMITED, retryAfterSeconds = retryAfter)
            status in 500..599 -> ApiOutcome.Failure(FailureKind.SERVER)
            else -> ApiOutcome.Failure(FailureKind.REJECTED)
        }
    }

    /**
     * Attach a human correction to a collected sample. Called only when a
     * transcription returned a sample id (contribution on AND collected),
     * so there is always something to correct. The corrected text is sent
     * EXACTLY as the user entered it — the server keeps original_transcript
     * immutable and evolves current_transcript. Blocking; off the main
     * thread. No retry: a correction is a deliberate user act, not a
     * background operation.
     */
    fun correct(sampleId: String, correctedText: String): CorrectionOutcome {
        val key = apiKey()?.takeIf { it.isNotBlank() }
            ?: return CorrectionOutcome.Failure(FailureKind.NO_API_KEY)
        val base = baseUrl().trim().trimEnd('/')
        if (base.isEmpty()) return CorrectionOutcome.Failure(FailureKind.NO_BASE_URL)

        val payload = JSONObject().put("corrected_text", correctedText).toString()
        val request = Request.Builder()
            .url("$base/v1/audio/transcriptions/$sampleId/correction")
            .header("Authorization", "Bearer $key")
            .header("X-IntelliAI-Client", "keyboard/1.0")
            .post(payload.toRequestBody("application/json".toMediaType()))
            .build()
        return try {
            http.newCall(request).execute().use { response ->
                interpretCorrection(response.code, response)
            }
        } catch (_: IOException) {
            CorrectionOutcome.Failure(FailureKind.NETWORK)
        }
    }

    private fun interpretCorrection(status: Int, response: okhttp3.Response): CorrectionOutcome {
        if (status in 200..299) return CorrectionOutcome.Success
        val error = runCatching {
            JSONObject(response.body?.string().orEmpty()).getJSONObject("error")
        }.getOrNull()
        return when (error?.optString("type").orEmpty()) {
            "authentication_error" -> CorrectionOutcome.Failure(FailureKind.BAD_API_KEY)
            // The sample is gone or belongs to another org (404, never
            // existence-disclosing): nothing here to correct.
            "resource_not_found_error" -> CorrectionOutcome.Failure(FailureKind.SAMPLE_UNAVAILABLE)
            "invalid_request_error" -> CorrectionOutcome.Failure(FailureKind.REJECTED)
            "rate_limit_error" -> CorrectionOutcome.Failure(FailureKind.RATE_LIMITED)
            else -> CorrectionOutcome.Failure(
                if (status == 401) FailureKind.BAD_API_KEY else FailureKind.SERVER
            )
        }
    }
}

/** What a transcription attempt produced, in product terms. */
sealed interface ApiOutcome {
    data class Success(val text: String, val sampleId: String?) : ApiOutcome

    data class Failure(
        val kind: FailureKind,
        val serverMessage: String? = null,
        val retryAfterSeconds: Int? = null,
    ) : ApiOutcome
}

/** What a correction attempt produced. */
sealed interface CorrectionOutcome {
    data object Success : CorrectionOutcome

    data class Failure(val kind: FailureKind) : CorrectionOutcome
}

enum class FailureKind {
    NO_API_KEY, // no key configured / server saw none
    NO_BASE_URL, // release build with no server configured
    BAD_API_KEY, // invalid, revoked, or expired
    QUOTA, // monthly allowance exhausted — retrying never helps
    RATE_LIMITED, // slow down; Retry-After says when
    UNAVAILABLE, // 503 family — briefly retryable
    REJECTED, // the request itself was refused (validation, language…)
    NO_SPEECH, // 200 with empty text: nothing recognizable was said
    SAMPLE_UNAVAILABLE, // the sample to correct no longer exists
    NETWORK, // could not reach IntelliAI at all
    SERVER, // 5xx without a parseable envelope
}
