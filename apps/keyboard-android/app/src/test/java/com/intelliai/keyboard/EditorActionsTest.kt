package com.intelliai.keyboard

import android.text.InputType
import android.view.inputmethod.EditorInfo
import com.intelliai.keyboard.keyboard.EnterBehavior
import com.intelliai.keyboard.keyboard.deletionLengthBefore
import com.intelliai.keyboard.keyboard.dictationCommitText
import com.intelliai.keyboard.keyboard.enterBehavior
import org.junit.Assert.assertEquals
import org.junit.Test

/**
 * The enter and backspace decision logic — pure functions over the
 * compile-time constants of EditorInfo/InputType, so they run on the
 * plain JVM with no Android runtime.
 */
class EditorActionsTest {

    @Test
    fun `multiline editors always get a newline even with an action set`() {
        val multiline = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_MULTI_LINE
        assertEquals(
            EnterBehavior.Newline,
            enterBehavior(EditorInfo.IME_ACTION_SEND, multiline),
        )
    }

    @Test
    fun `editors with an IME action perform it`() {
        val text = InputType.TYPE_CLASS_TEXT
        assertEquals(
            EnterBehavior.Action(EditorInfo.IME_ACTION_SEARCH),
            enterBehavior(EditorInfo.IME_ACTION_SEARCH, text),
        )
        assertEquals(
            EnterBehavior.Action(EditorInfo.IME_ACTION_GO),
            enterBehavior(EditorInfo.IME_ACTION_GO, text),
        )
        assertEquals(
            EnterBehavior.Action(EditorInfo.IME_ACTION_NEXT),
            enterBehavior(EditorInfo.IME_ACTION_NEXT, text),
        )
    }

    @Test
    fun `no action or explicit no-enter-action flag means newline`() {
        val text = InputType.TYPE_CLASS_TEXT
        assertEquals(EnterBehavior.Newline, enterBehavior(EditorInfo.IME_ACTION_NONE, text))
        assertEquals(EnterBehavior.Newline, enterBehavior(EditorInfo.IME_ACTION_UNSPECIFIED, text))
        assertEquals(
            EnterBehavior.Newline,
            enterBehavior(
                EditorInfo.IME_ACTION_SEND or EditorInfo.IME_FLAG_NO_ENTER_ACTION,
                text,
            ),
        )
    }

    @Test
    fun `backspace deletes one character normally`() {
        assertEquals(1, deletionLengthBefore("hello"))
        assertEquals(1, deletionLengthBefore("a"))
    }

    @Test
    fun `backspace deletes a whole surrogate pair`() {
        // An emoji is two UTF-16 code units; deleting one would leave a
        // broken half-character in the target app's field.
        assertEquals(2, deletionLengthBefore("hi 👍"))
        assertEquals(2, deletionLengthBefore("😀"))
    }

    @Test
    fun `backspace does nothing at the start of the field`() {
        assertEquals(0, deletionLengthBefore(""))
        assertEquals(0, deletionLengthBefore(null))
    }

    // ── Dictation spacing: simple and predictable, never clever ─────

    @Test
    fun `dictation after a word gets exactly one joining space`() {
        assertEquals(" there", dictationCommitText("Hello", "there"))
        assertEquals(" 42", dictationCommitText("answer:", "42"))
    }

    @Test
    fun `dictation into an empty field or after whitespace is untouched`() {
        assertEquals("Hello", dictationCommitText(null, "Hello"))
        assertEquals("Hello", dictationCommitText("", "Hello"))
        assertEquals("world", dictationCommitText("Hello ", "world"))
        assertEquals("line", dictationCommitText("first\n", "line"))
    }

    @Test
    fun `the transcript itself is never modified`() {
        // IntelliAI STT's own punctuation, casing, and spacing survive.
        assertEquals(" Hello, how are you?", dictationCommitText("Hi", "Hello, how are you?"))
        assertEquals("", dictationCommitText("Hi", ""))
    }
}
