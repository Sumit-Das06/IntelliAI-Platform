package com.intelliai.keyboard.settings

import android.content.SharedPreferences

/**
 * A minimal key-value seam for the keyboard's NON-secret settings, so
 * [KeyboardSettings]' language/server logic is unit-testable on the JVM
 * with an in-memory fake — no Robolectric, no emulator, no new
 * dependency. Production wraps SharedPreferences; the secret API key
 * uses EncryptedSharedPreferences directly and is verified on-device.
 */
interface KeyValueStore {
    fun getString(key: String): String?
    fun putString(key: String, value: String)
}

class SharedPrefsKeyValueStore(private val prefs: SharedPreferences) : KeyValueStore {
    override fun getString(key: String): String? = prefs.getString(key, null)
    override fun putString(key: String, value: String) {
        prefs.edit().putString(key, value).apply()
    }
}
