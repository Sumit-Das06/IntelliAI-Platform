package com.intelliai.keyboard

import com.intelliai.keyboard.api.ApiOutcome
import com.intelliai.keyboard.api.FailureKind
import com.intelliai.keyboard.audio.Recorder
import com.intelliai.keyboard.dictation.DictationController
import com.intelliai.keyboard.dictation.DictationError
import com.intelliai.keyboard.dictation.DictationState
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.TestScope
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.advanceUntilIdle
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The dictation state machine on virtual time: every transition —
 * including the 60-second auto-stop — runs deterministically on the
 * JVM with fake seams for the recorder, the API, and permissions.
 */
@OptIn(ExperimentalCoroutinesApi::class)
class DictationControllerTest {

    private class FakeRecorder(
        var startSucceeds: Boolean = true,
        var result: Recorder.Recording? = Recorder.Recording(ByteArray(32_000), 1_000),
    ) : Recorder {
        var released = false
        var stopped = false
        override fun start(): Boolean = startSucceeds
        override fun stop(): Recorder.Recording? {
            stopped = true
            return result
        }
        override fun release() {
            released = true
        }
    }

    private class FakeGate(var granted: Boolean, var autoRespond: Boolean = true) :
        DictationController.PermissionGate {
        var requested = false
        var respond: ((Boolean) -> Unit)? = null
        override fun hasRecordPermission(): Boolean = granted
        override fun requestRecordPermission() {
            requested = true
            respond?.invoke(granted)
        }
    }

    private class FakeListener : DictationController.Listener {
        val states = mutableListOf<DictationState>()
        val transcripts = mutableListOf<String>()
        override fun onStateChanged(state: DictationState) {
            states.add(state)
        }
        override fun onTranscript(text: String) {
            transcripts.add(text)
        }
        fun errors(): List<DictationError> =
            states.filterIsInstance<DictationState.IdleWithError>().map { it.error }
    }

    private fun harness(
        recorder: FakeRecorder = FakeRecorder(),
        gate: FakeGate = FakeGate(granted = true),
        hasKey: Boolean = true,
        outcome: ApiOutcome = ApiOutcome.Success("hello world", sampleId = null),
        scope: TestScope,
    ): Triple<DictationController, FakeListener, FakeRecorder> {
        val listener = FakeListener()
        val dispatcher = StandardTestDispatcher(scope.testScheduler)
        val controller = DictationController(
            scope = scope,
            recorder = recorder,
            transcribe = { outcome },
            permissions = gate,
            hasApiKey = { hasKey },
            listener = listener,
            ioDispatcher = dispatcher,
        )
        return Triple(controller, listener, recorder)
    }

    @Test
    fun `happy path - idle to recording to processing to transcript to idle`() {
        val scope = TestScope()
        val (controller, listener, recorder) = harness(scope = scope)

        controller.onMicTapped()
        assertTrue(controller.state is DictationState.Recording)

        controller.onMicTapped() // stop
        assertEquals(DictationState.Processing, controller.state)
        assertTrue(recorder.stopped)

        scope.advanceUntilIdle()
        assertEquals(listOf("hello world"), listener.transcripts)
        assertEquals(DictationState.Idle, controller.state)
    }

    @Test
    fun `no api key fails before touching the microphone`() {
        val scope = TestScope()
        val gate = FakeGate(granted = true)
        val (controller, listener, recorder) = harness(hasKey = false, gate = gate, scope = scope)

        controller.onMicTapped()

        assertEquals(listOf(DictationError.NO_API_KEY), listener.errors())
        assertEquals(DictationState.Idle, controller.state)
        assertTrue(!gate.requested && !recorder.stopped)
    }

    @Test
    fun `permission is requested once and granted continues into recording`() {
        val scope = TestScope()
        val gate = FakeGate(granted = false, autoRespond = false)
        val (controller, _, _) = harness(gate = gate, scope = scope)

        controller.onMicTapped()
        assertEquals(DictationState.RequestingPermission, controller.state)
        assertTrue(gate.requested)

        gate.granted = true
        controller.onPermissionResult(true)
        assertTrue(controller.state is DictationState.Recording)
    }

    @Test
    fun `permission denied lands on the honest error and idle`() {
        val scope = TestScope()
        val gate = FakeGate(granted = false, autoRespond = false)
        val (controller, listener, _) = harness(gate = gate, scope = scope)

        controller.onMicTapped()
        controller.onPermissionResult(false)

        assertEquals(listOf(DictationError.PERMISSION_DENIED), listener.errors())
        assertEquals(DictationState.Idle, controller.state)
    }

    @Test
    fun `recorder failure is reported, not crashed`() {
        val scope = TestScope()
        val (controller, listener, _) =
            harness(recorder = FakeRecorder(startSucceeds = false), scope = scope)

        controller.onMicTapped()

        assertEquals(listOf(DictationError.RECORDER_UNAVAILABLE), listener.errors())
        assertEquals(DictationState.Idle, controller.state)
    }

    @Test
    fun `a fumbled tap - under half a second - never reaches the api`() {
        val scope = TestScope()
        val recorder = FakeRecorder(result = Recorder.Recording(ByteArray(3200), durationMs = 100))
        val (controller, listener, _) = harness(recorder = recorder, scope = scope)

        controller.onMicTapped()
        controller.onMicTapped()
        scope.advanceUntilIdle()

        assertEquals(listOf(DictationError.NO_SPEECH_RECORDED), listener.errors())
        assertTrue(listener.transcripts.isEmpty())
    }

    @Test
    fun `api failure maps to its dictation error`() {
        val scope = TestScope()
        val (controller, listener, _) = harness(
            outcome = ApiOutcome.Failure(FailureKind.QUOTA),
            scope = scope,
        )

        controller.onMicTapped()
        controller.onMicTapped()
        scope.advanceUntilIdle()

        assertEquals(listOf(DictationError.QUOTA_EXHAUSTED), listener.errors())
        assertEquals(DictationState.Idle, controller.state)
        assertTrue(listener.transcripts.isEmpty())
    }

    @Test
    fun `recording elapsed ticks flow to the ui`() {
        val scope = TestScope()
        val (controller, listener, _) = harness(scope = scope)

        controller.onMicTapped()
        scope.advanceTimeBy(1_100)

        val elapsed = listener.states.filterIsInstance<DictationState.Recording>().map { it.elapsedMs }
        assertTrue("expected ticks, got $elapsed", elapsed.any { it >= 1_000 })
        controller.cancel()
    }

    @Test
    fun `the 60 second cap stops recording and still processes the speech`() {
        val scope = TestScope()
        val (controller, listener, recorder) = harness(scope = scope)

        controller.onMicTapped()
        scope.advanceTimeBy(DictationController.MAX_RECORDING_MS + 1_000)
        scope.advanceUntilIdle()

        assertTrue(recorder.stopped) // auto-stopped at the cap…
        assertEquals(listOf("hello world"), listener.transcripts) // …and NOT discarded
        assertEquals(DictationState.Idle, controller.state)
    }

    @Test
    fun `taps while processing are ignored`() {
        val scope = TestScope()
        val (controller, listener, _) = harness(scope = scope)

        controller.onMicTapped()
        controller.onMicTapped() // → Processing
        controller.onMicTapped() // noise
        controller.onMicTapped() // noise
        scope.advanceUntilIdle()

        assertEquals(listOf("hello world"), listener.transcripts) // exactly once
    }

    @Test
    fun `cancel during recording releases the microphone and returns to idle`() {
        val scope = TestScope()
        val (controller, listener, recorder) = harness(scope = scope)

        controller.onMicTapped()
        controller.cancel()

        assertTrue(recorder.released)
        assertEquals(DictationState.Idle, controller.state)
        assertTrue(listener.transcripts.isEmpty())
        scope.advanceUntilIdle() // no zombie ticker fires afterwards
        assertEquals(DictationState.Idle, controller.state)
    }
}
