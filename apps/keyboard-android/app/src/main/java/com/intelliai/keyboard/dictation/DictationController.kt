package com.intelliai.keyboard.dictation

import com.intelliai.keyboard.api.ApiOutcome
import com.intelliai.keyboard.api.FailureKind
import com.intelliai.keyboard.audio.Recorder
import com.intelliai.keyboard.audio.WavEncoder
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/**
 * The dictation state machine — explicit states, no scattered booleans.
 *
 *     Idle → RequestingPermission → Recording → Processing → Idle
 *                        ↘ (denied)      ↘ (error)   ↘ (failure)
 *                          Idle+error      Idle+error   Idle+error
 *
 * Pure of Android types: the recorder, the API, permissions, and even
 * time are injected seams, so every transition — including the
 * 60-second auto-stop — is unit-tested on the JVM with virtual time.
 * The service supplies the Android realities and consumes two outputs:
 * state changes (for the keyboard UI) and transcripts (for the
 * InputConnection).
 */
class DictationController(
    private val scope: CoroutineScope,
    private val recorder: Recorder,
    private val transcribe: suspend (wav: ByteArray, language: String?) -> ApiOutcome,
    private val permissions: PermissionGate,
    private val hasApiKey: () -> Boolean,
    private val listener: Listener,
    // The API language tag to use, read fresh at each dictation START and
    // then LOCKED for that request (null = Auto = omit the field).
    private val languageTag: () -> String? = { null },
    private val ioDispatcher: CoroutineDispatcher = Dispatchers.IO,
) {

    interface PermissionGate {
        fun hasRecordPermission(): Boolean

        /** Launch the trampoline; the result comes back via [onPermissionResult]. */
        fun requestRecordPermission()
    }

    interface Listener {
        fun onStateChanged(state: DictationState)

        /** A non-blank transcript, ready for the InputConnection. */
        fun onTranscript(text: String)
    }

    var state: DictationState = DictationState.Idle
        private set

    private var tickerJob: Job? = null

    // Locked when recording starts; changing the language selection
    // afterward cannot alter the request already in flight.
    private var capturedLanguageTag: String? = null

    /** One button, state-dependent meaning: start, or stop. */
    fun onMicTapped() {
        when (state) {
            // IdleWithError is a listener-only decoration; the machine
            // itself rests at Idle — both mean "ready to start".
            is DictationState.Idle, is DictationState.IdleWithError -> beginDictation()
            is DictationState.Recording -> finishRecording()
            // A tap while asking or processing is noise, not a command.
            is DictationState.RequestingPermission, is DictationState.Processing -> Unit
        }
    }

    fun onPermissionResult(granted: Boolean) {
        if (state !is DictationState.RequestingPermission) return
        if (granted) startRecording() else fail(DictationError.PERMISSION_DENIED)
    }

    /** Service teardown or keyboard hidden: stop hardware, drop audio,
     *  cancel any in-flight work. Always safe. */
    fun cancel() {
        tickerJob?.cancel()
        tickerJob = null
        recorder.release()
        moveTo(DictationState.Idle)
    }

    private fun beginDictation() {
        if (!hasApiKey()) {
            fail(DictationError.NO_API_KEY)
            return
        }
        if (permissions.hasRecordPermission()) {
            startRecording()
        } else {
            moveTo(DictationState.RequestingPermission)
            permissions.requestRecordPermission()
        }
    }

    private fun startRecording() {
        if (!recorder.start()) {
            fail(DictationError.RECORDER_UNAVAILABLE)
            return
        }
        // Lock the language at the moment dictation begins — the request
        // will use THIS value even if the user changes the selection
        // while it records or processes.
        capturedLanguageTag = languageTag()
        moveTo(DictationState.Recording(elapsedMs = 0))
        tickerJob = scope.launch {
            var elapsed = 0L
            while (elapsed < MAX_RECORDING_MS) {
                delay(TICK_MS)
                elapsed += TICK_MS
                if (state !is DictationState.Recording) return@launch
                moveTo(DictationState.Recording(elapsed))
            }
            // Cap reached: stop and PROCESS what was said — a hard stop
            // that discards a minute of speech would be theft.
            finishRecording()
        }
    }

    private fun finishRecording() {
        tickerJob?.cancel()
        tickerJob = null
        val recording = recorder.stop()
        if (recording == null || recording.durationMs < MIN_RECORDING_MS) {
            fail(DictationError.NO_SPEECH_RECORDED)
            return
        }
        moveTo(DictationState.Processing)
        val language = capturedLanguageTag
        scope.launch {
            val wav = WavEncoder.wrapPcm16(recording.pcm)
            val outcome = withContext(ioDispatcher) { transcribe(wav, language) }
            when (outcome) {
                is ApiOutcome.Success -> {
                    listener.onTranscript(outcome.text)
                    moveTo(DictationState.Idle)
                }
                is ApiOutcome.Failure -> fail(
                    DictationError.fromApi(outcome.kind),
                    outcome.serverMessage,
                )
            }
        }
    }

    private fun fail(error: DictationError, serverMessage: String? = null) {
        moveTo(DictationState.Idle, error, serverMessage)
    }

    private fun moveTo(
        next: DictationState,
        error: DictationError? = null,
        serverMessage: String? = null,
    ) {
        state = next
        listener.onStateChanged(
            if (error != null) DictationState.IdleWithError(error, serverMessage) else next
        )
        if (error != null) state = DictationState.Idle
    }

    companion object {
        /** 60 s: generous for dictation (a long spoken paragraph),
         *  ~1.9 MB of WAV — far under the platform's 25 MB / 600 s
         *  runtime caps — and a hard bound on how long a keyboard can
         *  possibly hold the microphone. */
        const val MAX_RECORDING_MS = 60_000L

        /** Below half a second there is no utterance — don't bill the
         *  user's quota for a fumbled tap. */
        const val MIN_RECORDING_MS = 500L

        const val TICK_MS = 250L
    }
}

/** The keyboard-facing states. IdleWithError is Idle plus one transient
 *  human explanation — the state machine never gets stuck in error. */
sealed interface DictationState {
    data object Idle : DictationState
    data object RequestingPermission : DictationState
    data class Recording(val elapsedMs: Long) : DictationState
    data object Processing : DictationState
    data class IdleWithError(val error: DictationError, val serverMessage: String?) :
        DictationState
}

enum class DictationError {
    NO_API_KEY,
    NO_BASE_URL,
    PERMISSION_DENIED,
    RECORDER_UNAVAILABLE,
    NO_SPEECH_RECORDED,
    NO_SPEECH_RECOGNIZED,
    BAD_API_KEY,
    QUOTA_EXHAUSTED,
    RATE_LIMITED,
    SERVICE_UNAVAILABLE,
    REQUEST_REJECTED,
    NETWORK,
    SERVER;

    companion object {
        fun fromApi(kind: FailureKind): DictationError = when (kind) {
            FailureKind.NO_API_KEY -> NO_API_KEY
            FailureKind.NO_BASE_URL -> NO_BASE_URL
            FailureKind.BAD_API_KEY -> BAD_API_KEY
            FailureKind.QUOTA -> QUOTA_EXHAUSTED
            FailureKind.RATE_LIMITED -> RATE_LIMITED
            FailureKind.UNAVAILABLE -> SERVICE_UNAVAILABLE
            FailureKind.REJECTED -> REQUEST_REJECTED
            FailureKind.NO_SPEECH -> NO_SPEECH_RECOGNIZED
            FailureKind.NETWORK -> NETWORK
            FailureKind.SERVER -> SERVER
        }
    }
}
