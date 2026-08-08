package com.intelliai.keyboard.setup

/**
 * Enablement truth, derived from the real system state — never from a
 * stored boolean. MainActivity feeds this from InputMethodManager's
 * enabled-IME list and Settings.Secure.DEFAULT_INPUT_METHOD; the
 * derivation itself is pure so it can be pinned by unit tests.
 *
 * IME ids look like "com.intelliai.keyboard/.service.IntelliAIKeyboardService";
 * ownership is decided by the package component before the slash.
 */
data class ImeStatus(val enabled: Boolean, val selected: Boolean)

fun imeStatus(
    enabledImeIds: List<String>,
    selectedImeId: String?,
    packageName: String,
): ImeStatus {
    val ownsId = { id: String -> id.substringBefore('/') == packageName }
    return ImeStatus(
        enabled = enabledImeIds.any(ownsId),
        selected = selectedImeId != null && ownsId(selectedImeId),
    )
}
