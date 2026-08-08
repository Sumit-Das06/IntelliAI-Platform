package com.intelliai.keyboard.dictation

import android.Manifest
import android.os.Bundle
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity

/**
 * The microphone-permission trampoline. An InputMethodService cannot
 * host the runtime-permission dialog, so the keyboard launches this
 * fully transparent activity; the user sees only Android's own dialog.
 * The verdict travels back over an in-process callback and the activity
 * disappears (noHistory, excludeFromRecents, no animation).
 */
class PermissionActivity : AppCompatActivity() {

    private val request =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
            deliver(granted)
            finish()
            overridePendingTransition(0, 0)
        }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        request.launch(Manifest.permission.RECORD_AUDIO)
    }

    companion object {
        /** Set by the keyboard service before launching; consumed once.
         *  In-process only — the IME and this activity share a process. */
        @Volatile
        var pendingResult: ((Boolean) -> Unit)? = null

        private fun deliver(granted: Boolean) {
            pendingResult?.invoke(granted)
            pendingResult = null
        }
    }
}
