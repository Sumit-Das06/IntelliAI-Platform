package com.intelliai.keyboard.settings

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import com.intelliai.keyboard.BuildConfig

/**
 * The keyboard's two settings, stored in EncryptedSharedPreferences —
 * the API key is a bearer credential and must never sit in plaintext
 * prefs. Backed by an Android Keystore master key (AES256-GCM); if the
 * Keystore is unavailable the store reports itself unusable rather than
 * silently falling back to plaintext.
 *
 * The full key is write-only from the UI's point of view: callers get
 * [apiKeyHint] (prefix + last four) for display and [apiKey] only at
 * request-building time. Nothing here logs.
 */
class KeyboardSettings private constructor(private val prefs: SharedPreferences) {

    fun apiKey(): String? = prefs.getString(KEY_API_KEY, null)?.takeIf { it.isNotBlank() }

    fun hasApiKey(): Boolean = apiKey() != null

    /** Display form only: "ik_live_…wxyz" — never the credential. */
    fun apiKeyHint(): String? = apiKey()?.let { key ->
        val firstUnderscore = key.indexOf('_')
        val secondUnderscore = if (firstUnderscore >= 0) key.indexOf('_', firstUnderscore + 1) else -1
        val prefix = if (secondUnderscore > 0) key.take(secondUnderscore + 1) else key.take(3)
        "$prefix…${key.takeLast(4)}"
    }

    fun setApiKey(key: String) {
        prefs.edit().putString(KEY_API_KEY, key.trim()).apply()
    }

    fun baseUrl(): String =
        prefs.getString(KEY_BASE_URL, null)?.takeIf { it.isNotBlank() }
            ?: BuildConfig.DEFAULT_BASE_URL

    fun setBaseUrl(url: String) {
        prefs.edit().putString(KEY_BASE_URL, url.trim().trimEnd('/')).apply()
    }

    companion object {
        private const val KEY_API_KEY = "api_key"
        private const val KEY_BASE_URL = "base_url"

        /** Null when the Keystore cannot back the store — callers show
         *  an honest error instead of degrading to plaintext. */
        fun open(context: Context): KeyboardSettings? = try {
            val masterKey = MasterKey.Builder(context.applicationContext)
                .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
                .build()
            KeyboardSettings(
                EncryptedSharedPreferences.create(
                    context.applicationContext,
                    "intelliai_keyboard_secure",
                    masterKey,
                    EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
                    EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
                )
            )
        } catch (_: Exception) {
            null
        }
    }
}
