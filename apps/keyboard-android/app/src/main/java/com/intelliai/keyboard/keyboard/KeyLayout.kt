package com.intelliai.keyboard.keyboard

/**
 * The keyboard's layout facts, as pure data — no Android types, so the
 * shape of the keyboard is unit-testable on the JVM.
 *
 * Two layers only (letters and numbers/symbols): an MVP earns a second
 * symbols page when someone misses a character, not before.
 */
object KeyLayout {

    enum class Layer { LETTERS, SYMBOLS }

    /** QWERTY rows, lowercase; shift is a presentation transform. */
    val LETTER_ROWS: List<String> = listOf(
        "qwertyuiop",
        "asdfghjkl",
        "zxcvbnm",
    )

    /** The symbol layer: digits on top, then the characters people
     *  actually reach for while messaging. */
    val SYMBOL_ROWS: List<String> = listOf(
        "1234567890",
        "@#\$_&-+()/",
        "*\"':;!?",
    )

    fun rows(layer: Layer): List<String> = when (layer) {
        Layer.LETTERS -> LETTER_ROWS
        Layer.SYMBOLS -> SYMBOL_ROWS
    }

    /** What a key press should commit, given the shift state. Symbols
     *  never shift — only letters carry case. */
    fun output(key: Char, shifted: Boolean): String =
        if (shifted && key.isLetter()) key.uppercaseChar().toString() else key.toString()
}
