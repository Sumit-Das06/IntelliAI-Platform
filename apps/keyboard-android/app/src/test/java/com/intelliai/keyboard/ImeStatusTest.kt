package com.intelliai.keyboard

import com.intelliai.keyboard.setup.imeStatus
import org.junit.Assert.assertEquals
import org.junit.Test

class ImeStatusTest {

    private val ourId = "com.intelliai.keyboard/.service.IntelliAIKeyboardService"
    private val gboardId = "com.google.android.inputmethod.latin/.LatinIME"

    @Test
    fun `not enabled when the system list lacks our IME`() {
        val status = imeStatus(listOf(gboardId), gboardId, "com.intelliai.keyboard")
        assertEquals(false, status.enabled)
        assertEquals(false, status.selected)
    }

    @Test
    fun `enabled but not selected`() {
        val status = imeStatus(listOf(gboardId, ourId), gboardId, "com.intelliai.keyboard")
        assertEquals(true, status.enabled)
        assertEquals(false, status.selected)
    }

    @Test
    fun `enabled and selected`() {
        val status = imeStatus(listOf(gboardId, ourId), ourId, "com.intelliai.keyboard")
        assertEquals(true, status.enabled)
        assertEquals(true, status.selected)
    }

    @Test
    fun `selection is decided by package, never by string luck`() {
        // A hostile or coincidental id containing our name must not match.
        val impostor = "com.intelliai.keyboard.fake/.EvilIME"
        val status = imeStatus(listOf(impostor), impostor, "com.intelliai.keyboard")
        assertEquals(false, status.enabled)
        assertEquals(false, status.selected)
    }

    @Test
    fun `null selected id means not selected`() {
        val status = imeStatus(listOf(ourId), null, "com.intelliai.keyboard")
        assertEquals(true, status.enabled)
        assertEquals(false, status.selected)
    }
}
