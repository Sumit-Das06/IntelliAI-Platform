package com.intelliai.keyboard

import com.intelliai.keyboard.keyboard.KeyLayout
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class KeyLayoutTest {

    @Test
    fun `letter layer carries all 26 letters exactly once`() {
        val letters = KeyLayout.LETTER_ROWS.joinToString("").toList()
        assertEquals(26, letters.size)
        assertEquals(26, letters.toSet().size)
        assertTrue(letters.all { it in 'a'..'z' })
    }

    @Test
    fun `letter rows are the QWERTY shape`() {
        assertEquals(listOf("qwertyuiop", "asdfghjkl", "zxcvbnm"), KeyLayout.LETTER_ROWS)
    }

    @Test
    fun `symbol layer leads with the digits row`() {
        assertEquals("1234567890", KeyLayout.SYMBOL_ROWS.first())
        assertTrue(KeyLayout.SYMBOL_ROWS.all { it.isNotEmpty() })
    }

    @Test
    fun `shift capitalizes letters only`() {
        assertEquals("A", KeyLayout.output('a', shifted = true))
        assertEquals("a", KeyLayout.output('a', shifted = false))
        // Symbols never shift — only letters carry case.
        assertEquals("1", KeyLayout.output('1', shifted = true))
        assertEquals("@", KeyLayout.output('@', shifted = true))
    }

    @Test
    fun `rows resolves the requested layer`() {
        assertEquals(KeyLayout.LETTER_ROWS, KeyLayout.rows(KeyLayout.Layer.LETTERS))
        assertEquals(KeyLayout.SYMBOL_ROWS, KeyLayout.rows(KeyLayout.Layer.SYMBOLS))
    }
}
