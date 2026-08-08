package com.intelliai.keyboard.keyboard

import android.text.InputType
import android.view.inputmethod.EditorInfo

/**
 * Pure decisions about how the keyboard behaves against an editor —
 * kept free of live Android objects so they are unit-testable. (The
 * EditorInfo/InputType values used here are compile-time constants,
 * inlined by the compiler, so these functions run on a plain JVM.)
 */

/** What the enter key should do for the current editor. */
sealed interface EnterBehavior {
    /** Commit a newline — multiline editors and editors with no action. */
    data object Newline : EnterBehavior

    /** Perform the editor's IME action (send, search, done, go, next…). */
    data class Action(val actionId: Int) : EnterBehavior
}

fun enterBehavior(imeOptions: Int, inputType: Int): EnterBehavior {
    val isText = inputType and InputType.TYPE_MASK_CLASS == InputType.TYPE_CLASS_TEXT
    val multiline = isText && inputType and InputType.TYPE_TEXT_FLAG_MULTI_LINE != 0
    if (multiline) return EnterBehavior.Newline
    if (imeOptions and EditorInfo.IME_FLAG_NO_ENTER_ACTION != 0) return EnterBehavior.Newline
    return when (val action = imeOptions and EditorInfo.IME_MASK_ACTION) {
        EditorInfo.IME_ACTION_NONE, EditorInfo.IME_ACTION_UNSPECIFIED -> EnterBehavior.Newline
        else -> EnterBehavior.Action(action)
    }
}

/**
 * How many characters backspace should delete before the cursor.
 *
 * One, except when the text ends in a surrogate pair (emoji and every
 * other astral-plane character) — deleting one code unit there would
 * leave a broken half-character in the field.
 */
fun deletionLengthBefore(textBeforeCursor: CharSequence?): Int {
    if (textBeforeCursor.isNullOrEmpty()) return 0
    if (textBeforeCursor.length >= 2) {
        val last = textBeforeCursor[textBeforeCursor.length - 1]
        val beforeLast = textBeforeCursor[textBeforeCursor.length - 2]
        if (Character.isSurrogatePair(beforeLast, last)) return 2
    }
    return 1
}
