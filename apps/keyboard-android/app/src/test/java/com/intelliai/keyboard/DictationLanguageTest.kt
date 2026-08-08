package com.intelliai.keyboard

import com.intelliai.keyboard.dictation.DictationLanguage
import com.intelliai.keyboard.settings.KeyValueStore
import com.intelliai.keyboard.settings.KeyboardSettings
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/**
 * The canonical language mapping and its persistence — the two facts
 * that decide what IntelliAI STT is told. Pure JVM: the language model
 * has no Android types, and persistence is exercised through an
 * in-memory [KeyValueStore] (the real SharedPreferences plumbing is
 * verified on the emulator).
 */
class DictationLanguageTest {

    private class InMemoryStore : KeyValueStore {
        val map = mutableMapOf<String, String>()
        override fun getString(key: String): String? = map[key]
        override fun putString(key: String, value: String) {
            map[key] = value
        }
    }

    // ── The mapping: Auto → omit, English → en, Hindi → hi, Arabic → ar

    @Test
    fun `auto maps to no api tag - the field must be omitted`() {
        assertNull(DictationLanguage.AUTO.apiTag)
    }

    @Test
    fun `english hindi arabic map to en hi ar`() {
        assertEquals("en", DictationLanguage.ENGLISH.apiTag)
        assertEquals("hi", DictationLanguage.HINDI.apiTag)
        assertEquals("ar", DictationLanguage.ARABIC.apiTag)
    }

    @Test
    fun `exactly these four languages exist - no others can reach the api`() {
        assertEquals(
            listOf("auto", "en", "hi", "ar"),
            DictationLanguage.entries.map { it.prefValue },
        )
        // No regional/country suffixes — the base subtags only.
        assertEquals(
            setOf(null, "en", "hi", "ar"),
            DictationLanguage.entries.map { it.apiTag }.toSet(),
        )
    }

    @Test
    fun `the default is auto`() {
        assertEquals(DictationLanguage.AUTO, DictationLanguage.DEFAULT)
        assertEquals(DictationLanguage.AUTO, DictationLanguage.fromPref(null))
        assertEquals(DictationLanguage.AUTO, DictationLanguage.fromPref("nonsense"))
    }

    @Test
    fun `pref values round-trip`() {
        for (language in DictationLanguage.entries) {
            assertEquals(language, DictationLanguage.fromPref(language.prefValue))
        }
    }

    // ── Persistence through KeyboardSettings ────────────────────────

    @Test
    fun `a fresh install defaults to auto`() {
        val settings = KeyboardSettings(InMemoryStore(), secure = null)
        assertEquals(DictationLanguage.AUTO, settings.language())
    }

    @Test
    fun `a selection persists across settings instances over the same store`() {
        val store = InMemoryStore()
        KeyboardSettings(store, secure = null).setLanguage(DictationLanguage.HINDI)

        // A new instance over the same backing store — as the keyboard
        // and the settings screen each open their own — sees the choice.
        val reopened = KeyboardSettings(store, secure = null)
        assertEquals(DictationLanguage.HINDI, reopened.language())
    }

    @Test
    fun `keyboard and settings share one source of truth`() {
        // Both surfaces open KeyboardSettings over the same prefs. Model
        // that with two instances over one store: a write on one is a
        // read on the other, in both directions.
        val store = InMemoryStore()
        val keyboardSide = KeyboardSettings(store, secure = null)
        val settingsSide = KeyboardSettings(store, secure = null)

        settingsSide.setLanguage(DictationLanguage.ARABIC)
        assertEquals(DictationLanguage.ARABIC, keyboardSide.language())

        keyboardSide.setLanguage(DictationLanguage.ENGLISH)
        assertEquals(DictationLanguage.ENGLISH, settingsSide.language())
    }
}
