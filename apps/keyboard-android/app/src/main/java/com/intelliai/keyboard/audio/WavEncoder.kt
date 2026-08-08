package com.intelliai.keyboard.audio

import java.io.ByteArrayOutputStream

/**
 * PCM16 → WAV container, as a pure function — no Android types, fully
 * unit-tested. The backend's canonical pipeline resamples everything
 * server-side, so the keyboard ships exactly what it recorded: 16 kHz,
 * mono, 16-bit little-endian PCM in a standard RIFF/WAVE/fmt/data
 * layout. No client-side resampling, no encoders, no audio libraries.
 */
object WavEncoder {

    const val SAMPLE_RATE_HZ = 16_000
    const val CHANNELS = 1
    const val BITS_PER_SAMPLE = 16

    fun wrapPcm16(
        pcm: ByteArray,
        sampleRateHz: Int = SAMPLE_RATE_HZ,
        channels: Int = CHANNELS,
    ): ByteArray {
        val bytesPerSample = BITS_PER_SAMPLE / 8
        val byteRate = sampleRateHz * channels * bytesPerSample
        val blockAlign = channels * bytesPerSample
        val out = ByteArrayOutputStream(44 + pcm.size)

        out.writeAscii("RIFF")
        out.writeIntLe(36 + pcm.size) // RIFF chunk size: rest of file
        out.writeAscii("WAVE")

        out.writeAscii("fmt ")
        out.writeIntLe(16) // PCM fmt chunk length
        out.writeShortLe(1) // audio format 1 = linear PCM
        out.writeShortLe(channels)
        out.writeIntLe(sampleRateHz)
        out.writeIntLe(byteRate)
        out.writeShortLe(blockAlign)
        out.writeShortLe(BITS_PER_SAMPLE)

        out.writeAscii("data")
        out.writeIntLe(pcm.size)
        out.write(pcm)

        return out.toByteArray()
    }

    /** Duration the PCM payload represents, for limits and UX. */
    fun durationMs(pcmByteCount: Int, sampleRateHz: Int = SAMPLE_RATE_HZ): Long {
        val bytesPerSecond = sampleRateHz * CHANNELS * (BITS_PER_SAMPLE / 8)
        return pcmByteCount * 1000L / bytesPerSecond
    }

    private fun ByteArrayOutputStream.writeAscii(text: String) =
        write(text.toByteArray(Charsets.US_ASCII))

    private fun ByteArrayOutputStream.writeIntLe(value: Int) {
        write(value and 0xFF)
        write(value ushr 8 and 0xFF)
        write(value ushr 16 and 0xFF)
        write(value ushr 24 and 0xFF)
    }

    private fun ByteArrayOutputStream.writeShortLe(value: Int) {
        write(value and 0xFF)
        write(value ushr 8 and 0xFF)
    }
}
