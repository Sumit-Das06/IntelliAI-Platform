package com.intelliai.keyboard.setup

import android.content.ActivityNotFoundException
import android.content.Context
import android.os.Bundle
import android.provider.Settings
import android.view.inputmethod.InputMethodManager
import android.widget.Button
import android.widget.EditText
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import com.intelliai.keyboard.BuildConfig
import com.intelliai.keyboard.R
import com.intelliai.keyboard.settings.KeyboardSettings

/**
 * Setup and onboarding — NOT the keyboard itself.
 *
 * Guides: enable IntelliAI in Android's keyboard list → select it as
 * the current keyboard → verify. Status is derived from the REAL
 * system state (InputMethodManager + Settings.Secure) on every
 * resume/focus — never from a stored flag, so it is honest the moment
 * the user returns from Android Settings.
 */
class MainActivity : AppCompatActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        findViewById<Button>(R.id.enable_button).setOnClickListener {
            try {
                startActivity(android.content.Intent(Settings.ACTION_INPUT_METHOD_SETTINGS))
            } catch (_: ActivityNotFoundException) {
                Toast.makeText(this, R.string.setup_settings_unavailable, Toast.LENGTH_SHORT).show()
            }
        }
        findViewById<Button>(R.id.select_button).setOnClickListener {
            inputMethodManager().showInputMethodPicker()
        }

        setUpApiSection()
    }

    /** The IntelliAI API card: key (write-only, encrypted at rest) and
     *  server address. The full key is never displayed after saving —
     *  only a prefix+last-four hint in the status line. */
    private fun setUpApiSection() {
        val settings = KeyboardSettings.open(this)
        val urlInput = findViewById<EditText>(R.id.api_url_input)
        val keyInput = findViewById<EditText>(R.id.api_key_input)
        val feedback = findViewById<TextView>(R.id.api_feedback)

        if (settings == null) {
            feedback.text = getString(R.string.api_error_storage)
            findViewById<Button>(R.id.api_save_button).isEnabled = false
            return
        }
        urlInput.setText(settings.baseUrl())
        refreshApiStatus(settings)

        findViewById<Button>(R.id.api_save_button).setOnClickListener {
            feedback.text = ""
            val url = urlInput.text.toString().trim()
            when {
                url.isEmpty() && BuildConfig.DEFAULT_BASE_URL.isEmpty() ->
                    feedback.text = getString(R.string.api_error_bad_url)
                url.isNotEmpty() && !url.startsWith("http://") && !url.startsWith("https://") ->
                    feedback.text = getString(R.string.api_error_bad_url)
                url.startsWith("http://") && !BuildConfig.DEBUG ->
                    // Release builds never talk cleartext — the network
                    // security config enforces it; this message explains it.
                    feedback.text = getString(R.string.api_error_https_required)
                else -> {
                    settings.setBaseUrl(url)
                    val key = keyInput.text.toString().trim()
                    if (key.isNotEmpty()) {
                        settings.setApiKey(key)
                        keyInput.text.clear() // the credential leaves the screen
                    }
                    refreshApiStatus(settings)
                    feedback.text = getString(R.string.api_saved)
                }
            }
        }
    }

    private fun refreshApiStatus(settings: KeyboardSettings) {
        val status = findViewById<TextView>(R.id.api_status)
        val hint = settings.apiKeyHint()
        if (hint != null) {
            status.text = getString(R.string.api_status_configured, hint)
            status.setTextColor(ContextCompat.getColor(this, R.color.setup_ok))
        } else {
            status.text = getString(R.string.api_status_missing)
            status.setTextColor(ContextCompat.getColor(this, R.color.setup_muted))
        }
    }

    override fun onResume() {
        super.onResume()
        refreshStatus()
    }

    override fun onWindowFocusChanged(hasFocus: Boolean) {
        super.onWindowFocusChanged(hasFocus)
        // The IME picker is a system dialog that never pauses this
        // activity — focus return is the only signal a choice was made.
        if (hasFocus) refreshStatus()
    }

    private fun refreshStatus() {
        val status = imeStatus(
            enabledImeIds = inputMethodManager().enabledInputMethodList.map { it.id },
            selectedImeId = Settings.Secure.getString(
                contentResolver,
                Settings.Secure.DEFAULT_INPUT_METHOD,
            ),
            packageName = packageName,
        )

        val enabledLine = findViewById<TextView>(R.id.status_enabled)
        enabledLine.text = getString(
            if (status.enabled) R.string.status_enabled else R.string.status_not_enabled
        )
        enabledLine.setTextColor(statusColor(status.enabled))

        val selectedLine = findViewById<TextView>(R.id.status_selected)
        selectedLine.text = getString(
            if (status.selected) R.string.status_selected else R.string.status_not_selected
        )
        selectedLine.setTextColor(statusColor(status.selected))
    }

    private fun statusColor(ok: Boolean): Int =
        ContextCompat.getColor(this, if (ok) R.color.setup_ok else R.color.setup_muted)

    private fun inputMethodManager(): InputMethodManager =
        getSystemService(Context.INPUT_METHOD_SERVICE) as InputMethodManager
}
