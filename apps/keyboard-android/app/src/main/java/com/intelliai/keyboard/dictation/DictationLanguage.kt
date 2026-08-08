package com.intelliai.keyboard.dictation

/**
 * The dictation languages the user can choose — the single canonical
 * mapping between a UI choice and what IntelliAI STT is told.
 *
 * Pure of Android types so the mapping is unit-tested on the JVM;
 * friendly display names live in string resources (a UI concern), and
 * only these four values can ever reach the API — arbitrary language
 * strings never travel through the app.
 *
 *     Auto    → apiTag null → the `language` field is OMITTED (server detects)
 *     English → "en"
 *     Hindi   → "hi"
 *     Arabic  → "ar"
 *
 * ``apiTag`` uses the platform's canonical base subtags (the server
 * normalizes anyway); ``indicator`` is the compact keyboard chip label.
 */
enum class DictationLanguage(
    val apiTag: String?,
    val prefValue: String,
    val indicator: String,
) {
    AUTO(apiTag = null, prefValue = "auto", indicator = "Auto"),
    ENGLISH(apiTag = "en", prefValue = "en", indicator = "EN"),
    HINDI(apiTag = "hi", prefValue = "hi", indicator = "HI"),
    ARABIC(apiTag = "ar", prefValue = "ar", indicator = "AR");

    companion object {
        val DEFAULT = AUTO

        /** Resolve a persisted preference back to a choice; unknown or
         *  absent values fall back to the default (Auto) so a new
         *  install — or a corrupted value — is always Auto. */
        fun fromPref(value: String?): DictationLanguage =
            entries.firstOrNull { it.prefValue == value } ?: DEFAULT
    }
}
