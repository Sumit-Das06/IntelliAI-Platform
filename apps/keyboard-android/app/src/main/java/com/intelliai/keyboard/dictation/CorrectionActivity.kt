package com.intelliai.keyboard.dictation

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.text.InputType
import android.view.WindowManager
import android.widget.EditText
import android.widget.FrameLayout
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import com.intelliai.keyboard.R

/**
 * The correction editor, as a real activity — the same trampoline
 * pattern [PermissionActivity] uses, and for the same underlying
 * reason: **an InputMethodService cannot host its own editable
 * dialog.**
 *
 * The first attempt (13D) showed the editor from the service itself, as
 * an AlertDialog attached to the IME window with
 * ``FLAG_ALT_FOCUSABLE_IM``. That flag is correct for [LanguagePicker]
 * — a list you tap, needing no keyboard — but it is exactly wrong for a
 * text field: it forbids the window from interacting with any input
 * method. On a physical device the consequences were:
 *
 * 1. tapping the field summoned no keyboard for the dialog;
 * 2. typing went to the HOST app's field instead (the IME was still
 *    bound there);
 * 3. that input churn fired ``onFinishInputView``, tearing down the
 *    input view;
 * 4. the dialog was attached to that view's window token, so the window
 *    manager destroyed it mid-edit.
 *
 * Emulator verification missed all of this because it drove the editor
 * with ``adb shell input text``, which injects below the focus layer and
 * never asks a keyboard to appear. Found on the first physical device,
 * 10 Aug 2026.
 *
 * An activity has its own window and its own focus, so ANY keyboard —
 * including IntelliAI's own — can serve it normally. The correction
 * travels back over the same in-process callback [PermissionActivity]
 * uses; the service owns the actual API call.
 */
class CorrectionActivity : AppCompatActivity() {

    private var delivered = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val transcript = intent.getStringExtra(EXTRA_TRANSCRIPT).orEmpty()

        val input = EditText(this).apply {
            setText(transcript)
            setSelection(text.length)
            inputType = InputType.TYPE_CLASS_TEXT or
                InputType.TYPE_TEXT_FLAG_MULTI_LINE or
                InputType.TYPE_TEXT_FLAG_CAP_SENTENCES
            setSingleLine(false)
            maxLines = 6
        }
        val pad = (16 * resources.displayMetrics.density).toInt()
        val container = FrameLayout(this).apply {
            setPadding(pad, pad / 2, pad, 0)
            addView(input)
        }

        val dialog = AlertDialog.Builder(this)
            .setTitle(R.string.correction_dialog_title)
            .setView(container)
            .setPositiveButton(R.string.correction_save) { _, _ ->
                // Sent EXACTLY as entered — no punctuation, casing, or
                // spacing normalization.
                val corrected = input.text.toString()
                if (corrected.isNotBlank()) deliver(corrected)
            }
            .setNegativeButton(android.R.string.cancel, null)
            .create()
        // Dismissing by any route (Save, Cancel, back, outside tap) ends
        // the activity exactly once.
        dialog.setOnDismissListener { finishQuietly() }
        dialog.show()
        // Focus the field and ask for the keyboard immediately: the user
        // tapped "Edit" to type, so make typing possible without a
        // second tap.
        input.requestFocus()
        dialog.window?.setSoftInputMode(
            WindowManager.LayoutParams.SOFT_INPUT_STATE_ALWAYS_VISIBLE
        )
    }

    private fun deliver(corrected: String) {
        if (delivered) return
        delivered = true
        pendingCorrection?.invoke(corrected)
        pendingCorrection = null
    }

    private fun finishQuietly() {
        // A dismissal without Save is a cancellation: drop the callback
        // so a stale closure can never fire later.
        if (!delivered) pendingCorrection = null
        finish()
        overridePendingTransition(0, 0)
    }

    override fun onDestroy() {
        if (!delivered) pendingCorrection = null
        super.onDestroy()
    }

    companion object {
        private const val EXTRA_TRANSCRIPT = "transcript"

        /** Set by the keyboard service before launching; consumed once.
         *  In-process only — the IME and this activity share a process. */
        @Volatile
        var pendingCorrection: ((String) -> Unit)? = null

        /** Launch the editor for [transcript]; [onSave] receives the
         *  corrected text verbatim, or is never called if the user
         *  cancels. */
        fun start(context: Context, transcript: String, onSave: (String) -> Unit) {
            pendingCorrection = onSave
            context.startActivity(
                Intent(context, CorrectionActivity::class.java)
                    .putExtra(EXTRA_TRANSCRIPT, transcript)
                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            )
        }
    }
}
