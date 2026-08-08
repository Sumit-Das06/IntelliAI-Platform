package com.intelliai.keyboard.service

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.inputmethodservice.InputMethodService
import android.os.Build
import android.view.ContextThemeWrapper
import android.view.View
import android.view.inputmethod.EditorInfo
import android.view.inputmethod.InputMethodManager
import androidx.core.content.ContextCompat
import com.intelliai.keyboard.R
import com.intelliai.keyboard.api.CorrectionOutcome
import com.intelliai.keyboard.api.FailureKind
import com.intelliai.keyboard.api.IntelliAIApiClient
import com.intelliai.keyboard.audio.WavRecorder
import com.intelliai.keyboard.dictation.CorrectionDialog
import com.intelliai.keyboard.dictation.DictationController
import com.intelliai.keyboard.dictation.DictationError
import com.intelliai.keyboard.dictation.DictationLanguage
import com.intelliai.keyboard.dictation.DictationState
import com.intelliai.keyboard.dictation.LanguagePicker
import com.intelliai.keyboard.dictation.PermissionActivity
import com.intelliai.keyboard.dictation.contentDescription
import com.intelliai.keyboard.keyboard.EnterBehavior
import com.intelliai.keyboard.keyboard.KeyLayout
import com.intelliai.keyboard.keyboard.KeyboardView
import com.intelliai.keyboard.keyboard.deletionLengthBefore
import com.intelliai.keyboard.keyboard.dictationCommitText
import com.intelliai.keyboard.keyboard.enterBehavior
import com.intelliai.keyboard.settings.KeyboardSettings
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/**
 * The IntelliAI input method — a real Android IME.
 *
 * The service owns the InputConnection and composes the seams: keyboard
 * view (pixels), dictation controller (state machine), recorder
 * (microphone), API client (IntelliAI STT). Every editor operation
 * guards against a null InputConnection: a keyboard must never crash
 * the app it is typing into.
 *
 * Privacy (13B law): audio is captured only between an explicit mic tap
 * and stop, lives only in memory, goes only to the configured IntelliAI
 * API, and is dropped when the request ends. Typed text is never
 * logged, stored, or transmitted. The API key appears only in the
 * Authorization header.
 */
class IntelliAIKeyboardService :
    InputMethodService(),
    KeyboardView.Listener,
    DictationController.Listener {

    private var keyboardView: KeyboardView? = null
    private var shifted = false
    private var layer = KeyLayout.Layer.LETTERS

    private lateinit var scope: CoroutineScope
    private var settings: KeyboardSettings? = null
    private var controller: DictationController? = null
    private var api: IntelliAIApiClient? = null

    // The last collected dictation, held IN MEMORY only so the user can
    // correct it. Never persisted; dropped when the input field changes
    // or the service is destroyed. Carries no audio and no API key.
    private data class CorrectionContext(val sampleId: String, val transcript: String)

    private var lastCorrection: CorrectionContext? = null

    override fun onCreate() {
        super.onCreate()
        scope = CoroutineScope(SupervisorJob() + Dispatchers.Main)
        settings = KeyboardSettings.open(this)
        val client = IntelliAIApiClient(
            baseUrl = { settings?.baseUrl().orEmpty() },
            apiKey = { settings?.apiKey() },
        )
        api = client
        controller = DictationController(
            scope = scope,
            recorder = WavRecorder(),
            transcribe = { wav, language, contribute -> client.transcribe(wav, language, contribute) },
            permissions = object : DictationController.PermissionGate {
                override fun hasRecordPermission(): Boolean =
                    ContextCompat.checkSelfPermission(
                        this@IntelliAIKeyboardService,
                        Manifest.permission.RECORD_AUDIO,
                    ) == PackageManager.PERMISSION_GRANTED

                override fun requestRecordPermission() {
                    PermissionActivity.pendingResult =
                        { granted -> controller?.onPermissionResult(granted) }
                    startActivity(
                        Intent(this@IntelliAIKeyboardService, PermissionActivity::class.java)
                            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                    )
                }
            },
            hasApiKey = { settings?.hasApiKey() == true },
            listener = this,
            // Read the persisted language at the moment dictation starts;
            // the controller locks it for that request. Auto (or no
            // settings) → null → the client omits the field.
            languageTag = { settings?.language()?.apiTag },
            // Likewise for contribution: captured at dictation start.
            contributionEnabled = { settings?.contributionEnabled() ?: true },
        )
    }

    private fun currentLanguage(): DictationLanguage =
        settings?.language() ?: DictationLanguage.DEFAULT

    private fun refreshLanguageIndicator() {
        val language = currentLanguage()
        keyboardView?.setLanguageIndicator(
            language.indicator,
            language.contentDescription(this),
        )
    }

    override fun onCreateInputView(): View =
        KeyboardView(this, this).also {
            keyboardView = it
            it.render(shifted, layer)
            refreshLanguageIndicator()
        }

    override fun onStartInputView(editorInfo: EditorInfo?, restarting: Boolean) {
        super.onStartInputView(editorInfo, restarting)
        layer = KeyLayout.Layer.LETTERS
        shifted = wantsInitialCaps(editorInfo)
        keyboardView?.render(shifted, layer)
        controller?.let { keyboardView?.setDictationState(it.state) }
        // The selection may have changed in Settings since the view was
        // built — reflect the persisted value every time we show.
        refreshLanguageIndicator()
    }

    private fun wantsInitialCaps(editorInfo: EditorInfo?): Boolean {
        val info = editorInfo ?: return false
        if (info.inputType == 0) return false
        val ic = currentInputConnection ?: return false
        return ic.getCursorCapsMode(info.inputType) != 0
    }

    // ── DictationController.Listener ────────────────────────────────

    override fun onStateChanged(state: DictationState) {
        keyboardView?.setDictationState(state)
        if (state is DictationState.IdleWithError) {
            keyboardView?.showTransientMessage(messageFor(state.error, state.serverMessage))
        }
    }

    override fun onTranscript(text: String, sampleId: String?) {
        val ic = currentInputConnection
        if (ic == null) {
            // The field went away while IntelliAI was thinking. Say so;
            // never crash, never type into the void.
            keyboardView?.showTransientMessage(getString(R.string.error_no_input_connection))
            return
        }
        ic.commitText(dictationCommitText(ic.getTextBeforeCursor(1, 0), text), 1)
        // A correction can only be offered when the backend actually
        // collected a sample (contribution on AND org consent on) — the
        // sample id is the sole, honest signal that something exists to
        // correct. No id → no offer.
        if (sampleId != null) {
            lastCorrection = CorrectionContext(sampleId, text)
            keyboardView?.showCorrectionOffer()
        } else {
            lastCorrection = null
        }
    }

    private fun messageFor(error: DictationError, serverMessage: String?): String = when (error) {
        DictationError.NO_API_KEY -> getString(R.string.error_no_api_key)
        DictationError.NO_BASE_URL -> getString(R.string.error_no_base_url)
        DictationError.PERMISSION_DENIED -> getString(R.string.error_permission_denied)
        DictationError.RECORDER_UNAVAILABLE -> getString(R.string.error_recorder_unavailable)
        DictationError.NO_SPEECH_RECORDED -> getString(R.string.error_no_speech_recorded)
        DictationError.NO_SPEECH_RECOGNIZED -> getString(R.string.error_no_speech_recognized)
        DictationError.BAD_API_KEY -> getString(R.string.error_bad_api_key)
        DictationError.QUOTA_EXHAUSTED -> getString(R.string.error_quota)
        DictationError.RATE_LIMITED -> getString(R.string.error_rate_limited)
        DictationError.SERVICE_UNAVAILABLE -> getString(R.string.error_service_unavailable)
        // The platform writes validation messages for humans (e.g. which
        // languages are served) and they carry no secrets.
        DictationError.REQUEST_REJECTED ->
            serverMessage?.takeIf { it.isNotBlank() } ?: getString(R.string.error_request_rejected)
        DictationError.NETWORK -> getString(R.string.error_network)
        DictationError.SERVER -> getString(R.string.error_server)
    }

    // ── KeyboardView.Listener ───────────────────────────────────────

    override fun onKey(key: Char) {
        val ic = currentInputConnection ?: return
        ic.commitText(KeyLayout.output(key, shifted), 1)
        if (shifted && key.isLetter()) {
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
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
            switchToNextInputMethod(false)
        } else {
            val imm = getSystemService(Context.INPUT_METHOD_SERVICE) as InputMethodManager
            imm.showInputMethodPicker()
        }
    }

    override fun onMicTapped() {
        controller?.onMicTapped()
    }

    override fun onLanguageChipTapped() {
        val view = keyboardView ?: return
        // Attach the picker to the IME window via the input view's token —
        // an InputMethodService cannot host a plain activity dialog.
        LanguagePicker.show(
            context = ContextThemeWrapper(this, R.style.Theme_IntelliAI),
            current = currentLanguage(),
            attachToken = view.windowToken,
        ) { chosen ->
            settings?.setLanguage(chosen)
            refreshLanguageIndicator()
        }
    }

    override fun onEditCorrection() {
        val view = keyboardView ?: return
        val correction = lastCorrection ?: return
        keyboardView?.hideCorrectionOffer()
        CorrectionDialog.show(
            context = ContextThemeWrapper(this, R.style.Theme_IntelliAI),
            transcript = correction.transcript,
            attachToken = view.windowToken,
        ) { corrected ->
            submitCorrection(correction.sampleId, corrected)
        }
    }

    override fun onDismissCorrection() {
        lastCorrection = null
    }

    private fun submitCorrection(sampleId: String, correctedText: String) {
        val client = api ?: return
        scope.launch {
            val outcome = withContext(Dispatchers.IO) { client.correct(sampleId, correctedText) }
            val message = when (outcome) {
                is CorrectionOutcome.Success -> getString(R.string.correction_saved)
                is CorrectionOutcome.Failure -> when (outcome.kind) {
                    FailureKind.SAMPLE_UNAVAILABLE -> getString(R.string.correction_unavailable)
                    FailureKind.BAD_API_KEY -> getString(R.string.error_bad_api_key)
                    FailureKind.NETWORK -> getString(R.string.error_network)
                    else -> getString(R.string.correction_failed)
                }
            }
            keyboardView?.showTransientMessage(message)
        }
        lastCorrection = null
    }

    // ── Lifecycle hygiene ───────────────────────────────────────────

    override fun onFinishInputView(finishingInput: Boolean) {
        // Keyboard hidden mid-recording: stop the hardware and drop the
        // audio — a hidden keyboard must never keep listening. The
        // pending correction context is for the field we're leaving.
        controller?.cancel()
        lastCorrection = null
        keyboardView?.hideCorrectionOffer()
        keyboardView?.releaseResources()
        super.onFinishInputView(finishingInput)
    }

    override fun onDestroy() {
        controller?.cancel()
        lastCorrection = null
        keyboardView?.releaseResources()
        keyboardView = null
        scope.cancel()
        super.onDestroy()
    }
}
