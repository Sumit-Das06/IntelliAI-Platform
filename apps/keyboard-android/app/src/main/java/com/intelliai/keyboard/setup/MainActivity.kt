package com.intelliai.keyboard.setup

import android.content.ActivityNotFoundException
import android.content.Context
import android.os.Bundle
import android.provider.Settings
import android.view.inputmethod.InputMethodManager
import android.widget.Button
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import com.intelliai.keyboard.R

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
