package com.intelliai.keyboard.keyboard

import android.annotation.SuppressLint
import android.content.Context
import android.graphics.Typeface
import android.os.Handler
import android.os.Looper
import android.util.TypedValue
import android.view.Gravity
import android.view.HapticFeedbackConstants
import android.view.MotionEvent
import android.view.View
import android.widget.ImageButton
import android.widget.LinearLayout
import android.widget.TextView
import androidx.core.content.ContextCompat
import com.intelliai.keyboard.R

/**
 * The IntelliAI keyboard surface — a plain custom view tree, built in
 * code. Deliberately NOT the deprecated android.inputmethodservice
 * .KeyboardView: rows of weighted key views over LinearLayout, which is
 * all a QWERTY MVP needs and is trivial to restyle.
 *
 * The view owns presentation only. Every semantic act (commit text,
 * delete, enter, layer/shift change, mic) is delegated to [Listener] —
 * the service owns the InputConnection and the state machine.
 */
@SuppressLint("ViewConstructor") // constructed by the service, never inflated
class KeyboardView(
    context: Context,
    private val listener: Listener,
) : LinearLayout(context) {

    interface Listener {
        fun onKey(key: Char)
        fun onBackspace()
        fun onEnter()
        fun onSpace()
        fun onShiftToggle()
        fun onLayerToggle()
        fun onSwitchKeyboard()
        fun onMicTapped()
        fun onLanguageChipTapped()
        fun onEditCorrection()
        fun onDismissCorrection()
    }

    private val handler = Handler(Looper.getMainLooper())
    private val brandLabel: TextView
    private val languageChip: TextView
    private val micButton: ImageButton
    private val rowsHost: LinearLayout
    private val correctionBar: LinearLayout
    private var revertBrandRunnable: Runnable? = null
    private var hideCorrectionRunnable: Runnable? = null
    private var dictationBrandActive = false

    private val keyHeight = dp(52)
    private val rowGap = dp(5)
    private val keyGap = dp(3)

    init {
        orientation = VERTICAL
        setBackgroundColor(color(R.color.kb_background))
        setPadding(dp(4), dp(6), dp(4), dp(8))

        // ── Branding / action bar ───────────────────────────────────
        val bar = LinearLayout(context).apply {
            orientation = HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            layoutParams = LayoutParams(LayoutParams.MATCH_PARENT, dp(44))
        }
        brandLabel = TextView(context).apply {
            text = context.getString(R.string.brand_bar)
            setTextColor(color(R.color.kb_brand_text))
            setTypeface(typeface, Typeface.BOLD)
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 16f)
            setPadding(dp(10), 0, dp(10), 0)
            layoutParams = LayoutParams(0, LayoutParams.WRAP_CONTENT, 1f)
        }
        // The dictation-language chip: compact, tappable, between the
        // brand and the mic (IntelliAI · Auto · 🎙). Starts at the
        // default; the service sets the persisted value on attach.
        languageChip = TextView(context).apply {
            text = context.getString(R.string.language_auto)
            setTextColor(color(R.color.kb_key_text))
            setTypeface(typeface, Typeface.BOLD)
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 13f)
            gravity = Gravity.CENTER
            minWidth = dp(52)
            background = ContextCompat.getDrawable(context, R.drawable.key_background_special)
            setPadding(dp(12), dp(6), dp(12), dp(6))
            isClickable = true
            isFocusable = true
            layoutParams = LayoutParams(LayoutParams.WRAP_CONTENT, LayoutParams.WRAP_CONTENT)
                .apply { marginEnd = dp(8) }
            setOnClickListener {
                it.performHapticFeedback(HapticFeedbackConstants.KEYBOARD_TAP)
                listener.onLanguageChipTapped()
            }
        }
        micButton = ImageButton(context).apply {
            setImageResource(R.drawable.ic_mic)
            background = ContextCompat.getDrawable(context, R.drawable.key_background_accent)
            contentDescription = context.getString(R.string.key_mic_description)
            layoutParams = LayoutParams(dp(38), dp(38)).apply { marginEnd = dp(6) }
            setOnClickListener {
                it.performHapticFeedback(HapticFeedbackConstants.KEYBOARD_TAP)
                listener.onMicTapped()
            }
        }
        bar.addView(brandLabel)
        bar.addView(languageChip)
        bar.addView(micButton)
        addView(bar)

        rowsHost = LinearLayout(context).apply {
            orientation = VERTICAL
            layoutParams = LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.WRAP_CONTENT)
        }
        addView(rowsHost)

        // A transient correction offer, GONE by default and shown at the
        // very top only after a dictation that actually produced a
        // collectible sample. It never appears otherwise, so it can't
        // clutter normal typing.
        correctionBar = buildCorrectionBar()
        addView(correctionBar, 0)
    }

    private fun buildCorrectionBar(): LinearLayout {
        val bar = LinearLayout(context).apply {
            orientation = HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            visibility = GONE
            setBackgroundColor(color(R.color.kb_key_special))
            setPadding(dp(12), dp(6), dp(8), dp(6))
            layoutParams = LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.WRAP_CONTENT)
        }
        bar.addView(
            TextView(context).apply {
                text = context.getString(R.string.correction_offer)
                setTextColor(color(R.color.kb_key_text))
                setTextSize(TypedValue.COMPLEX_UNIT_SP, 13f)
                layoutParams = LayoutParams(0, LayoutParams.WRAP_CONTENT, 1f)
            }
        )
        bar.addView(correctionAction(R.string.correction_edit, accent = true) {
            listener.onEditCorrection()
        })
        bar.addView(correctionAction(R.string.correction_dismiss, accent = false) {
            hideCorrectionOffer()
            listener.onDismissCorrection()
        })
        return bar
    }

    private fun correctionAction(labelRes: Int, accent: Boolean, onTap: () -> Unit): TextView =
        TextView(context).apply {
            text = context.getString(labelRes)
            gravity = Gravity.CENTER
            setTextColor(color(if (accent) R.color.kb_brand_text else R.color.kb_key_text_muted))
            setTypeface(typeface, Typeface.BOLD)
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 13f)
            setPadding(dp(14), dp(6), dp(14), dp(6))
            isClickable = true
            isFocusable = true
            background = ContextCompat.getDrawable(context, R.drawable.key_background)
            layoutParams = LayoutParams(LayoutParams.WRAP_CONTENT, LayoutParams.WRAP_CONTENT)
                .apply { marginStart = dp(6) }
            setOnClickListener {
                it.performHapticFeedback(HapticFeedbackConstants.KEYBOARD_TAP)
                onTap()
            }
        }

    /** Offer to correct the just-inserted transcript. Auto-dismisses so
     *  a stale offer never lingers over unrelated typing. */
    fun showCorrectionOffer() {
        correctionBar.visibility = VISIBLE
        hideCorrectionRunnable?.let(handler::removeCallbacks)
        val hide = Runnable { correctionBar.visibility = GONE }
        hideCorrectionRunnable = hide
        handler.postDelayed(hide, 9_000L)
    }

    fun hideCorrectionOffer() {
        hideCorrectionRunnable?.let(handler::removeCallbacks)
        correctionBar.visibility = GONE
    }

    /** Rebuild all key rows for the given state. Rare (shift/layer
     *  changes), so a rebuild is simpler and safer than in-place
     *  relabeling — there is nothing to get out of sync. */
    fun render(shifted: Boolean, layer: KeyLayout.Layer) {
        rowsHost.removeAllViews()
        val rows = KeyLayout.rows(layer)

        // Row 1 — 10 characters, full width.
        rowsHost.addView(characterRow(rows[0], shifted))

        // Row 2 — 9 letters get side insets; symbols run full width.
        rowsHost.addView(
            characterRow(
                rows[1],
                shifted,
                sideInset = if (layer == KeyLayout.Layer.LETTERS) 0.5f else 0f,
            )
        )

        // Row 3 — shift + characters + backspace.
        val row3 = newRow()
        row3.addView(
            specialKey(if (layer == KeyLayout.Layer.LETTERS) (if (shifted) "⬆" else "⇧") else "=\\<", 1.5f) {
                if (layer == KeyLayout.Layer.LETTERS) listener.onShiftToggle()
                // Symbols layer has no second page in the MVP; the key
                // is inert there but keeps the grid stable.
            }.also { it.contentDescription = context.getString(R.string.key_shift_description) }
        )
        rows[2].forEach { key -> row3.addView(characterKey(key, shifted, 1f)) }
        row3.addView(backspaceKey(1.5f))
        rowsHost.addView(row3)

        // Row 4 — layer, globe, space, period/comma, enter.
        val row4 = newRow()
        row4.addView(
            specialKey(if (layer == KeyLayout.Layer.LETTERS) "?123" else "ABC", 1.5f) {
                listener.onLayerToggle()
            }
        )
        row4.addView(
            specialKey("🌐", 1f) { listener.onSwitchKeyboard() }.also {
                it.contentDescription = context.getString(R.string.key_globe_description)
            }
        )
        row4.addView(spaceKey(4f))
        row4.addView(characterKey(if (layer == KeyLayout.Layer.LETTERS) '.' else ',', shifted = false, weight = 1f))
        row4.addView(enterKey(1.5f))
        rowsHost.addView(row4)
    }

    /** Update the language chip's label (compact, e.g. "Auto"/"HI") and
     *  its accessibility description ("Dictation language: Hindi"). */
    fun setLanguageIndicator(indicator: String, contentDescription: String) {
        languageChip.text = indicator
        languageChip.contentDescription = contentDescription
    }

    /** Swap the brand label for a transient message (dictation errors),
     *  reverting after a beat — unless a dictation state owns the bar. */
    fun showTransientMessage(message: String, millis: Long = 2600L) {
        revertBrandRunnable?.let(handler::removeCallbacks)
        brandLabel.text = message
        val revert = Runnable {
            if (!dictationBrandActive) brandLabel.text = context.getString(R.string.brand_bar)
        }
        revertBrandRunnable = revert
        handler.postDelayed(revert, millis)
    }

    /** Reflect the dictation state machine on the branding bar and the
     *  mic button. The user must always know whether the microphone is
     *  listening — the bar says so in words AND color. */
    fun setDictationState(state: com.intelliai.keyboard.dictation.DictationState) {
        when (state) {
            is com.intelliai.keyboard.dictation.DictationState.Recording -> {
                dictationBrandActive = true
                hideCorrectionOffer() // a new dictation supersedes the last offer
                revertBrandRunnable?.let(handler::removeCallbacks)
                val seconds = state.elapsedMs / 1000
                brandLabel.text = context.getString(R.string.dictation_listening) +
                    " · %d:%02d".format(seconds / 60, seconds % 60)
                brandLabel.setTextColor(color(R.color.kb_recording))
                micButton.setImageResource(R.drawable.ic_stop)
                micButton.contentDescription = context.getString(R.string.key_stop_description)
                micButton.isEnabled = true
                // The language is locked once dictation starts, so the
                // chip is inert while recording or processing.
                languageChip.isEnabled = false
            }
            is com.intelliai.keyboard.dictation.DictationState.Processing -> {
                dictationBrandActive = true
                revertBrandRunnable?.let(handler::removeCallbacks)
                brandLabel.text = context.getString(R.string.dictation_processing)
                brandLabel.setTextColor(color(R.color.kb_key_text_muted))
                micButton.setImageResource(R.drawable.ic_mic)
                micButton.isEnabled = false
                languageChip.isEnabled = false
            }
            else -> { // Idle, RequestingPermission, IdleWithError
                dictationBrandActive = false
                brandLabel.text = context.getString(R.string.brand_bar)
                brandLabel.setTextColor(color(R.color.kb_brand_text))
                micButton.setImageResource(R.drawable.ic_mic)
                micButton.contentDescription = context.getString(R.string.key_mic_description)
                micButton.isEnabled = true
                languageChip.isEnabled = true
            }
        }
    }

    fun releaseResources() {
        handler.removeCallbacksAndMessages(null)
    }

    // ── Row / key construction ──────────────────────────────────────

    private fun newRow(): LinearLayout = LinearLayout(context).apply {
        orientation = HORIZONTAL
        layoutParams = LayoutParams(LayoutParams.MATCH_PARENT, keyHeight).apply {
            topMargin = rowGap
        }
    }

    private fun characterRow(keys: String, shifted: Boolean, sideInset: Float = 0f): LinearLayout {
        val row = newRow()
        if (sideInset > 0f) row.addView(spacer(sideInset))
        keys.forEach { key -> row.addView(characterKey(key, shifted, 1f)) }
        if (sideInset > 0f) row.addView(spacer(sideInset))
        return row
    }

    private fun spacer(weight: Float): View = View(context).apply {
        layoutParams = LayoutParams(0, LayoutParams.MATCH_PARENT, weight)
    }

    private fun keyText(label: String, weight: Float, special: Boolean): TextView =
        TextView(context).apply {
            text = label
            gravity = Gravity.CENTER
            setTextColor(color(if (special) R.color.kb_key_text_muted else R.color.kb_key_text))
            setTextSize(TypedValue.COMPLEX_UNIT_SP, if (special) 14f else 20f)
            background = ContextCompat.getDrawable(
                context,
                if (special) R.drawable.key_background_special else R.drawable.key_background,
            )
            isClickable = true
            isFocusable = true
            layoutParams = LayoutParams(0, LayoutParams.MATCH_PARENT, weight).apply {
                marginStart = keyGap
                marginEnd = keyGap
            }
        }

    private fun characterKey(key: Char, shifted: Boolean, weight: Float): TextView =
        keyText(KeyLayout.output(key, shifted), weight, special = false).apply {
            setOnClickListener {
                it.performHapticFeedback(HapticFeedbackConstants.KEYBOARD_TAP)
                listener.onKey(key)
            }
        }

    private fun specialKey(label: String, weight: Float, onTap: () -> Unit): TextView =
        keyText(label, weight, special = true).apply {
            setOnClickListener {
                it.performHapticFeedbackCompat()
                onTap()
            }
        }

    private fun spaceKey(weight: Float): TextView =
        keyText(context.getString(R.string.key_space_label), weight, special = false).apply {
            setTextColor(color(R.color.kb_key_text_muted))
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 12f)
            setOnClickListener {
                it.performHapticFeedbackCompat()
                listener.onSpace()
            }
        }

    private fun enterKey(weight: Float): TextView =
        keyText("↵", weight, special = true).apply {
            contentDescription = context.getString(R.string.key_enter_description)
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 20f)
            setOnClickListener {
                it.performHapticFeedbackCompat()
                listener.onEnter()
            }
        }

    /** Backspace: tap deletes once; holding repeats after a beat —
     *  the one behavior a keyboard cannot ship without. */
    @SuppressLint("ClickableViewAccessibility") // press-and-hold semantics need raw touch
    private fun backspaceKey(weight: Float): TextView {
        val key = keyText("⌫", weight, special = true)
        key.contentDescription = context.getString(R.string.key_backspace_description)
        key.setTextSize(TypedValue.COMPLEX_UNIT_SP, 18f)

        var repeating = false
        val repeat = object : Runnable {
            override fun run() {
                if (!repeating) return
                listener.onBackspace()
                handler.postDelayed(this, 55L)
            }
        }
        key.setOnTouchListener { view, event ->
            when (event.actionMasked) {
                MotionEvent.ACTION_DOWN -> {
                    view.isPressed = true
                    view.performHapticFeedbackCompat()
                    listener.onBackspace()
                    repeating = true
                    handler.postDelayed({ if (repeating) handler.post(repeat) }, 400L)
                    true
                }
                MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> {
                    view.isPressed = false
                    repeating = false
                    true
                }
                else -> false
            }
        }
        return key
    }

    private fun View.performHapticFeedbackCompat() {
        performHapticFeedback(HapticFeedbackConstants.KEYBOARD_TAP)
    }

    private fun dp(value: Int): Int =
        (value * resources.displayMetrics.density).toInt()

    private fun color(res: Int): Int = ContextCompat.getColor(context, res)
}
