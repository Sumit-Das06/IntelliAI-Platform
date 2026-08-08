package com.intelliai.keyboard.settings

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import com.intelliai.keyboard.BuildConfig
import com.intelliai.keyboard.dictation.DictationLanguage

/**
 * The single source of truth for the keyboard's settings, split by
 * sensitivity behind one facade:
 *
 * - **Secret** (the API key, a bearer credential) lives in
 *   EncryptedSharedPreferences, Keystore-backed (AES256-GCM). If the
 *   Keystore is unavailable the secret store is simply absent
 *   ([secureStorageAvailable] is false) — never a silent plaintext
 *   fallback.
 * - **Non-secret** (dictation language, server address) lives in plain
 *   SharedPreferences, so those settings work even when the Keystore
 *   does not — the language is not a secret and does not belong in the
 *   encrypted store.
 *
 * Both the keyboard and the settings screen read and write through this
 * one class, so there is exactly one language state.
 */
class KeyboardSettings internal constructor(
    private val plain: KeyValueStore,
    private val secure: SharedPreferences?,
) {

    // ── Dictation language (non-secret) ─────────────────────────────

    fun language(): DictationLanguage =
        DictationLanguage.fromPref(plain.getString(KEY_LANGUAGE))

    fun setLanguage(language: DictationLanguage) {
        plain.putString(KEY_LANGUAGE, language.prefValue)
    }

    // ── Server address (non-secret) ─────────────────────────────────

    fun baseUrl(): String =
        plain.getString(KEY_BASE_URL)?.takeIf { it.isNotBlank() }
            ?: BuildConfig.DEFAULT_BASE_URL

    fun setBaseUrl(url: String) {
        plain.putString(KEY_BASE_URL, url.trim().trimEnd('/'))
    }

    // ── API key (secret) ────────────────────────────────────────────

    fun secureStorageAvailable(): Boolean = secure != null

    fun apiKey(): String? = secure?.getString(KEY_API_KEY, null)?.takeIf { it.isNotBlank() }

    fun hasApiKey(): Boolean = apiKey() != null

    /** Display form only: "ik_live_…wxyz" — never the credential. */
    fun apiKeyHint(): String? = apiKey()?.let { key ->
        val firstUnderscore = key.indexOf('_')
        val secondUnderscore = if (firstUnderscore >= 0) key.indexOf('_', firstUnderscore + 1) else -1
        val prefix = if (secondUnderscore > 0) key.take(secondUnderscore + 1) else key.take(3)
        "$prefix…${key.takeLast(4)}"
    }

    /** True if stored; false when the secure store is unavailable. */
    fun setApiKey(key: String): Boolean {
        val store = secure ?: return false
        store.edit().putString(KEY_API_KEY, key.trim()).apply()
        return true
    }

    companion object {
        private const val KEY_API_KEY = "api_key"
        private const val KEY_BASE_URL = "base_url"
        private const val KEY_LANGUAGE = "dictation_language"

        /** Always succeeds: plain prefs are always available, so
         *  language and server settings work regardless of Keystore
         *  state. The secure store is best-effort — check
         *  [secureStorageAvailable] before offering to save a key. */
        fun open(context: Context): KeyboardSettings {
            val app = context.applicationContext
            val plain = SharedPrefsKeyValueStore(
                app.getSharedPreferences("intelliai_keyboard_prefs", Context.MODE_PRIVATE)
            )
            val secure = try {
                val masterKey = MasterKey.Builder(app)
                    .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
                    .build()
                EncryptedSharedPreferences.create(
                    app,
                    "intelliai_keyboard_secure",
                    masterKey,
                    EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
                    EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
                )
            } catch (_: Exception) {
                null
            }
            return KeyboardSettings(plain, secure)
        }
    }
}
