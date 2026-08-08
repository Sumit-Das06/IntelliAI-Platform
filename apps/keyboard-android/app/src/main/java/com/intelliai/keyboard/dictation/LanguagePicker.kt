package com.intelliai.keyboard.dictation

import android.content.Context
import android.os.IBinder
import android.view.WindowManager
import androidx.annotation.StringRes
import androidx.appcompat.app.AlertDialog
import com.intelliai.keyboard.R

/**
 * The friendly, user-facing name of a dictation language — a UI concern,
 * kept out of the pure enum so the enum stays JVM-testable.
 */
@StringRes
fun DictationLanguage.friendlyNameRes(): Int = when (this) {
    DictationLanguage.AUTO -> R.string.language_auto
    DictationLanguage.ENGLISH -> R.string.language_english
    DictationLanguage.HINDI -> R.string.language_hindi
    DictationLanguage.ARABIC -> R.string.language_arabic
}

fun DictationLanguage.friendlyName(context: Context): String =
    context.getString(friendlyNameRes())

fun DictationLanguage.contentDescription(context: Context): String =
    context.getString(R.string.language_content_description, friendlyName(context))

/**
 * A lightweight single-choice language picker, native AlertDialog — no
 * new dependency. Used by both surfaces:
 *
 * - the settings Activity passes ``attachToken = null`` (a normal dialog);
 * - the keyboard passes its input view's window token, so the dialog can
 *   attach to the IME window (an InputMethodService cannot host a plain
 *   activity dialog — this is the standard attached-dialog pattern).
 *
 * Selection is immediate: pick → callback → dismiss. Theme-aware in
 * light and dark, and each row reads its friendly name to accessibility.
 */
object LanguagePicker {

    fun show(
        context: Context,
        current: DictationLanguage,
        attachToken: IBinder?,
        onPicked: (DictationLanguage) -> Unit,
    ) {
        val options = DictationLanguage.entries
        val labels = options.map { it.friendlyName(context) }.toTypedArray()
        val checked = options.indexOf(current)

        val dialog = AlertDialog.Builder(context)
            .setTitle(R.string.language_picker_title)
            .setSingleChoiceItems(labels, checked) { d, which ->
                onPicked(options[which])
                d.dismiss()
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
