package com.intelliai.keyboard.dictation

import android.content.Context
import android.os.IBinder
import android.text.InputType
import android.view.WindowManager
import android.widget.EditText
import android.widget.FrameLayout
import androidx.appcompat.app.AlertDialog
import com.intelliai.keyboard.R

/**
 * A minimal correction editor — a native AlertDialog with a single
 * multiline text field prefilled with the transcript. No transcript
 * history, no rich editor: the user fixes the text and saves. Attached
 * to the IME window via the input view's token (an InputMethodService
 * cannot host a plain activity dialog).
 *
 * The corrected text is passed back EXACTLY as entered — no punctuation,
 * casing, or spacing normalization. Saving replaces the sample's
 * current_transcript; it does NOT touch the text already inserted in the
 * host app.
 */
object CorrectionDialog {

    fun show(
        context: Context,
        transcript: String,
        attachToken: IBinder?,
        onSave: (String) -> Unit,
    ) {
        val input = EditText(context).apply {
            setText(transcript)
            setSelection(transcript.length)
            inputType = InputType.TYPE_CLASS_TEXT or
                InputType.TYPE_TEXT_FLAG_MULTI_LINE or
                InputType.TYPE_TEXT_FLAG_CAP_SENTENCES
            setSingleLine(false)
            maxLines = 4
            // Never let the user's own IntelliAI keyboard be summoned
            // recursively into this field — use the system default.
            // (No special handling needed: this dialog runs in-process
            // and the field simply accepts input from whatever IME shows.)
        }
        val pad = (16 * context.resources.displayMetrics.density).toInt()
        val container = FrameLayout(context).apply { setPadding(pad, pad / 2, pad, 0) }
        container.addView(input)

        val dialog = AlertDialog.Builder(context)
            .setTitle(R.string.correction_dialog_title)
            .setView(container)
            .setPositiveButton(R.string.correction_save) { _, _ ->
                val corrected = input.text.toString()
                if (corrected.isNotBlank()) onSave(corrected)
            }
            .setNegativeButton(android.R.string.cancel, null)
            .create()

        if (attachToken != null) {
            val window = requireNotNull(dialog.window)
            window.attributes = window.attributes.apply { token = attachToken }
            window.setType(WindowManager.LayoutParams.TYPE_APPLICATION_ATTACHED_DIALOG)
            window.addFlags(WindowManager.LayoutParams.FLAG_ALT_FOCUSABLE_IM)
        }
        dialog.show()
    }
}
