package com.intelliai.keyboard.service

import android.content.Context
import android.inputmethodservice.InputMethodService
import android.os.Build
import android.view.View
import android.view.inputmethod.EditorInfo
import android.view.inputmethod.InputMethodManager
import com.intelliai.keyboard.R
import com.intelliai.keyboard.keyboard.EnterBehavior
import com.intelliai.keyboard.keyboard.KeyLayout
import com.intelliai.keyboard.keyboard.KeyboardView
import com.intelliai.keyboard.keyboard.deletionLengthBefore
import com.intelliai.keyboard.keyboard.enterBehavior

/**
 * The IntelliAI input method — a real Android IME.
 *
 * The service owns the InputConnection and the tiny state machine
 * (shift, layer); the view owns pixels. Every editor operation guards
 * against a null InputConnection: a keyboard must never crash the app
 * it is typing into.
 *
 * Privacy (13A law): this service transmits nothing, records nothing,
 * and stores nothing. Typed text flows only through the system
 * InputConnection into the focused editor. The microphone button is an
 * honest placeholder — dictation arrives in Commit 13B.
 */
class IntelliAIKeyboardService : InputMethodService(), KeyboardView.Listener {

    private var keyboardView: KeyboardView? = null
    private var shifted = false
    private var layer = KeyLayout.Layer.LETTERS

    override fun onCreateInputView(): View =
        KeyboardView(this, this).also {
            keyboardView = it
            it.render(shifted, layer)
        }

    override fun onStartInputView(editorInfo: EditorInfo?, restarting: Boolean) {
        super.onStartInputView(editorInfo, restarting)
        // Fresh field, fresh state: letters layer, shift from the
        // editor's own capitalization mode (so an empty sentence field
        // starts capitalized, like every serious keyboard).
        layer = KeyLayout.Layer.LETTERS
        shifted = wantsInitialCaps(editorInfo)
        keyboardView?.render(shifted, layer)
    }

    private fun wantsInitialCaps(editorInfo: EditorInfo?): Boolean {
        val info = editorInfo ?: return false
        if (info.inputType == 0) return false
        val ic = currentInputConnection ?: return false
        return ic.getCursorCapsMode(info.inputType) != 0
    }

    // ── KeyboardView.Listener ───────────────────────────────────────

    override fun onKey(key: Char) {
        val ic = currentInputConnection ?: return
        ic.commitText(KeyLayout.output(key, shifted), 1)
        if (shifted && key.isLetter()) {
            // One-shot shift releases after the letter it capitalized.
            shifted = false
            keyboardView?.render(shifted, layer)
        }
    }

    override fun onSpace() {
        currentInputConnection?.commitText(" ", 1)
    }

    override fun onBackspace() {
        val ic = currentInputConnection ?: return
        val selected = ic.getSelectedText(0)
        if (!selected.isNullOrEmpty()) {
            // A selection is deleted as a unit — never text around it.
            ic.commitText("", 1)
            return
        }
        val length = deletionLengthBefore(ic.getTextBeforeCursor(2, 0))
        if (length > 0) ic.deleteSurroundingText(length, 0)
    }

    override fun onEnter() {
        val ic = currentInputConnection ?: return
        val info = currentInputEditorInfo
        when (val behavior = enterBehavior(info?.imeOptions ?: 0, info?.inputType ?: 0)) {
            is EnterBehavior.Newline -> ic.commitText("\n", 1)
            is EnterBehavior.Action -> ic.performEditorAction(behavior.actionId)
        }
    }

    override fun onShiftToggle() {
        shifted = !shifted
        keyboardView?.render(shifted, layer)
    }

    override fun onLayerToggle() {
        layer = when (layer) {
            KeyLayout.Layer.LETTERS -> KeyLayout.Layer.SYMBOLS
            KeyLayout.Layer.SYMBOLS -> KeyLayout.Layer.LETTERS
        }
        shifted = false
        keyboardView?.render(shifted, layer)
    }

    override fun onSwitchKeyboard() {
        // The globe key: hand off to the next IME like a good citizen;
        // older APIs get the system picker instead.
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
            switchToNextInputMethod(false)
        } else {
            val imm = getSystemService(Context.INPUT_METHOD_SERVICE) as InputMethodManager
            imm.showInputMethodPicker()
        }
    }

    override fun onMicTapped() {
        // 13A: an honest placeholder, nothing else. No permission, no
        // recording, no network. Dictation is Commit 13B.
        keyboardView?.showTransientMessage(getString(R.string.voice_coming_soon))
    }

    // ── Lifecycle hygiene ───────────────────────────────────────────

    override fun onFinishInputView(finishingInput: Boolean) {
        keyboardView?.releaseResources()
        super.onFinishInputView(finishingInput)
    }

    override fun onDestroy() {
        keyboardView?.releaseResources()
        keyboardView = null
        super.onDestroy()
    }
}
