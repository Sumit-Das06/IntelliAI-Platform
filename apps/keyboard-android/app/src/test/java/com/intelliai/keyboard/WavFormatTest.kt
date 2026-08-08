package com.intelliai.keyboard

import com.intelliai.keyboard.audio.WavEncoder
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Test

/**
 * The WAV container, byte for byte. The backend sniffs magic bytes
 * (RIFF….WAVE) before ffmpeg ever runs, so a malformed header means a
 * rejected dictation — this format is a wire contract, not a detail.
 */
class WavFormatTest {

    // Deterministic fixture: 1,000 samples of a ramp — 2,000 PCM bytes.
    private val pcm = ByteArray(2000) { index -> (index % 251).toByte() }
    private val wav = WavEncoder.wrapPcm16(pcm)

    private fun intLe(offset: Int): Int =
        (wav[offset].toInt() and 0xFF) or
            (wav[offset + 1].toInt() and 0xFF shl 8) or
            (wav[offset + 2].toInt() and 0xFF shl 16) or
            (wav[offset + 3].toInt() and 0xFF shl 24)

    private fun shortLe(offset: Int): Int =
        (wav[offset].toInt() and 0xFF) or (wav[offset + 1].toInt() and 0xFF shl 8)

    private fun ascii(offset: Int, length: Int): String =
        String(wav, offset, length, Charsets.US_ASCII)

    @Test
    fun `riff wave and chunk markers are in place`() {
        assertEquals("RIFF", ascii(0, 4))
        assertEquals("WAVE", ascii(8, 4))
        assertEquals("fmt ", ascii(12, 4))
        assertEquals("data", ascii(36, 4))
    }

    @Test
    fun `sizes are exact`() {
        assertEquals(44 + pcm.size, wav.size) // total file
        assertEquals(36 + pcm.size, intLe(4)) // RIFF chunk size
        assertEquals(16, intLe(16)) // fmt chunk length
        assertEquals(pcm.size, intLe(40)) // data length
    }

    @Test
    fun `format block declares 16kHz mono PCM16`() {
        assertEquals(1, shortLe(20)) // linear PCM
        assertEquals(1, shortLe(22)) // mono
        assertEquals(16_000, intLe(24)) // sample rate
        assertEquals(16_000 * 1 * 2, intLe(28)) // byte rate
        assertEquals(2, shortLe(32)) // block align = channels * 2
        assertEquals(16, shortLe(34)) // bits per sample
    }

    @Test
    fun `payload is the exact pcm, untouched`() {
        assertArrayEquals(pcm, wav.copyOfRange(44, wav.size))
    }

    @Test
    fun `duration math is bytes over byte rate`() {
        // 32,000 bytes/second at 16 kHz mono PCM16.
        assertEquals(1000L, WavEncoder.durationMs(32_000))
        assertEquals(62L, WavEncoder.durationMs(2000))
        assertEquals(0L, WavEncoder.durationMs(0))
    }
}
