package com.intelliai.keyboard.audio

import android.annotation.SuppressLint
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import java.io.ByteArrayOutputStream
import java.util.concurrent.atomic.AtomicBoolean

/**
 * Microphone capture: 16 kHz / mono / PCM16 via AudioRecord, read on a
 * dedicated thread, accumulated ONLY in memory. Privacy consequences of
 * that choice: dictation audio never touches disk, so there is nothing
 * to delete, nothing to forget, nothing another app could read. At the
 * 60-second cap the buffer peaks below 2 MB.
 *
 * The recorder is single-use per utterance: start() → stop(). stop()
 * and release() are safe to call in any state (idempotent) because the
 * IME's lifecycle can tear the keyboard down mid-recording.
 */
interface Recorder {
    /** True if capture actually started (mic available, permission held). */
    fun start(): Boolean

    /** Stop and return the captured PCM, or null if nothing was captured. */
    fun stop(): Recording?

    /** Unconditional teardown: stop hardware, discard audio. */
    fun release()

    data class Recording(val pcm: ByteArray, val durationMs: Long)
}

class WavRecorder : Recorder {

    private val recording = AtomicBoolean(false)
    private var audioRecord: AudioRecord? = null
    private var readerThread: Thread? = null
    private var buffer: ByteArrayOutputStream? = null

    // The one runtime permission this app has; the controller never
    // calls start() without it, and Android throws if that contract is
    // somehow broken — hence the lint suppression rather than a check
    // that could only be dead code here.
    @SuppressLint("MissingPermission")
    override fun start(): Boolean {
        if (recording.get()) return false
        val minBuffer = AudioRecord.getMinBufferSize(
            WavEncoder.SAMPLE_RATE_HZ,
            AudioFormat.CHANNEL_IN_MONO,
            AudioFormat.ENCODING_PCM_16BIT,
        )
        if (minBuffer <= 0) return false
        val record = try {
            AudioRecord(
                MediaRecorder.AudioSource.VOICE_RECOGNITION,
                WavEncoder.SAMPLE_RATE_HZ,
                AudioFormat.CHANNEL_IN_MONO,
                AudioFormat.ENCODING_PCM_16BIT,
                maxOf(minBuffer * 2, 8192),
            )
        } catch (_: Exception) {
            return false
        }
        if (record.state != AudioRecord.STATE_INITIALIZED) {
            record.release()
            return false
        }

        val sink = ByteArrayOutputStream()
        audioRecord = record
        buffer = sink
        recording.set(true)
        record.startRecording()

        readerThread = Thread({
            val chunk = ByteArray(4096)
            while (recording.get()) {
                val read = record.read(chunk, 0, chunk.size)
                if (read > 0) sink.write(chunk, 0, read) else if (read < 0) break
            }
        }, "intelliai-wav-recorder").also { it.start() }
        return true
    }

    override fun stop(): Recorder.Recording? {
        if (!recording.getAndSet(false)) return null
        readerThread?.join(1_000)
        readerThread = null
        val record = audioRecord
        audioRecord = null
        try {
            record?.stop()
        } catch (_: IllegalStateException) {
            // Already stopped by the system; the PCM we have is the PCM.
        }
        record?.release()
        val pcm = buffer?.toByteArray() ?: return null
        buffer = null
        if (pcm.isEmpty()) return null
        return Recorder.Recording(pcm, WavEncoder.durationMs(pcm.size))
    }

    override fun release() {
        recording.set(false)
        readerThread?.join(500)
        readerThread = null
        try {
            audioRecord?.stop()
        } catch (_: IllegalStateException) {
            // Teardown path — the hardware may already be gone.
        }
        audioRecord?.release()
        audioRecord = null
        buffer = null // the audio dies with the reference
    }
}
