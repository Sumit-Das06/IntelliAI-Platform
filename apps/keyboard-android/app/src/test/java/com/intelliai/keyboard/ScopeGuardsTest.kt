package com.intelliai.keyboard

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/**
 * The keyboard's scope guards, evolved milestone by milestone.
 * Networking and the microphone are DELIBERATE capabilities (asserted
 * positively, bounded exactly); everything beyond the keyboard's
 * client charter is a red build: heavyweight frameworks, telemetry,
 * disk-resident audio, logging, ML-lifecycle code, and internal
 * engine names.
 */
class ScopeGuardsTest {

    private val mainSources = File("src/main")
    private val mainManifest = File(mainSources, "AndroidManifest.xml")

    private fun mainFiles(vararg extensions: String): List<File> =
        mainSources.walkTopDown()
            .filter { it.isFile && it.extension in extensions }
            .toList()

    // ── Capabilities 13B earns, bounded exactly ─────────────────────

    @Test
    fun `the manifest declares exactly the two 13B permissions`() {
        val manifest = mainManifest.readText()
        val declared = Regex("""<uses-permission android:name="([^"]+)"""")
            .findAll(manifest)
            .map { it.groupValues[1] }
            .toSet()
        assertEquals(
            setOf("android.permission.RECORD_AUDIO", "android.permission.INTERNET"),
            declared,
        )
    }

    @Test
    fun `okhttp is the one networking library`() {
        Class.forName("okhttp3.OkHttpClient") // deliberate, present
        for (forbidden in listOf(
            "retrofit2.Retrofit",
            "com.android.volley.RequestQueue",
            "io.ktor.client.HttpClient",
            "androidx.work.WorkManager", // no background upload queues in 13B
            "com.google.firebase.FirebaseApp", // no telemetry, ever
        )) {
            try {
                Class.forName(forbidden)
                throw AssertionError("out-of-scope dependency present: $forbidden")
            } catch (_: ClassNotFoundException) {
                // exactly right
            }
        }
    }

    // ── Privacy invariants ──────────────────────────────────────────

    @Test
    fun `audio never touches disk`() {
        // The recorder accumulates PCM in memory only; nothing in main
        // sources opens files or names storage directories.
        val offenders = mainFiles("kt").filter { file ->
            val text = file.readText()
            text.contains("FileOutputStream") ||
                text.contains("filesDir") ||
                text.contains("cacheDir") ||
                text.contains("openFileOutput")
        }.map { it.name }
        assertEquals(emptyList<String>(), offenders)
    }

    @Test
    fun `nothing in the keyboard logs - anything`() {
        // A keyboard that logs is a keyboard that leaks: no android.util
        // .Log anywhere means no path by which keys, text, or audio
        // facts can reach logcat.
        val offenders = mainFiles("kt")
            .filter { it.readText().contains("android.util.Log") }
            .map { it.name }
        assertEquals(emptyList<String>(), offenders)
    }

    @Test
    fun `release builds cannot talk cleartext`() {
        // The main manifest carries no cleartext allowance and no
        // network security config — the debug overlay alone does.
        val manifest = mainManifest.readText()
        assertFalse(manifest.contains("usesCleartextTraffic"))
        assertFalse(manifest.contains("networkSecurityConfig"))
        val debugConfig = File("src/debug/res/xml/network_security_config.xml")
        assertTrue(debugConfig.isFile)
        assertTrue(debugConfig.readText().contains("10.0.2.2"))
    }

    // ── Scope fences: 13E is not started, engines stay invisible ────

    @Test
    fun `no fine-tuning or model-lifecycle code exists in the client`() {
        // 13D adds contribution + correction; it must not reach into the
        // future ML pipeline. The keyboard is a client — it never trains,
        // deploys, or names checkpoints.
        val forbidden = listOf(
            "fine-tun", "finetune", "training run", "train_model",
            "checkpoint", "gpu", "model promotion", "evaluation run",
        )
        val offenders = mainFiles("kt", "xml").filter { file ->
            val text = file.readText().lowercase()
            forbidden.any { text.contains(it) }
        }.map { it.name }
        assertEquals(emptyList<String>(), offenders)
    }

    @Test
    fun `no analytics or advertising sdk is on the classpath`() {
        for (forbidden in listOf(
            "com.google.firebase.analytics.FirebaseAnalytics",
            "com.google.android.gms.ads.MobileAds",
            "com.amplitude.api.Amplitude",
            "com.mixpanel.android.mpmetrics.MixpanelAPI",
        )) {
            try {
                Class.forName(forbidden)
                throw AssertionError("out-of-scope SDK present: $forbidden")
            } catch (_: ClassNotFoundException) {
                // exactly right
            }
        }
    }

    @Test
    fun `no internal engine name appears anywhere in sources or resources`() {
        val offenders = mainFiles("kt", "xml")
            .filter { it.readText().contains("whisper", ignoreCase = true) }
            .map { it.name }
        assertEquals(emptyList<String>(), offenders)
    }

    @Test
    fun `main sources exist where the build expects them`() {
        assertTrue(mainManifest.isFile)
        assertTrue(File(mainSources, "java/com/intelliai/keyboard").isDirectory)
    }
}
