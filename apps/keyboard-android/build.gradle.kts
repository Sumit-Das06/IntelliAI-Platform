// Root build file — plugin declarations only; all real configuration
// lives in :app. Single-module on purpose: an MVP keyboard does not
// earn a module graph.

plugins {
    alias(libs.plugins.android.application) apply false
    alias(libs.plugins.kotlin.android) apply false
}
