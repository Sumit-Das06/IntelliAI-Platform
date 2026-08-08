package com.intelliai.keyboard

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/**
 * 13A scope guards — executable statements of what this commit must
 * NOT contain. Dictation (audio capture, networking, permissions) is
 * Commit 13B; until then, these tests make scope creep a red build.
 */
class FoundationGuardsTest {

    // Gradle runs unit tests with the module directory as the working
    // directory, so the app's own sources are reachable relatively.
    private val mainSources = File("src/main")

    @Test
    fun `no networking library is on the classpath`() {
        for (forbidden in listOf(
            "okhttp3.OkHttpClient",
            "retrofit2.Retrofit",
            "com.android.volley.RequestQueue",
            "io.ktor.client.HttpClient",
        )) {
            try {
                Class.forName(forbidden)
                throw AssertionError("13A must ship no networking library, found: $forbidden")
            } catch (_: ClassNotFoundException) {
                // exactly right
            }
        }
    }

    @Test
    fun `the manifest requests no permissions at all`() {
        val manifest = File(mainSources, "AndroidManifest.xml").readText()
        assertFalse("13A must not request permissions", manifest.contains("<uses-permission"))
        assertFalse(manifest.contains("RECORD_AUDIO"))
        assertFalse(manifest.contains("android.permission.INTERNET"))
    }

    @Test
    fun `no audio capture code exists in main sources`() {
        val offenders = mainSources.walkTopDown()
            .filter { it.isFile && it.extension == "kt" }
            .filter { file ->
                val text = file.readText()
                text.contains("AudioRecord") || text.contains("MediaRecorder")
            }
            .map { it.name }
            .toList()
        assertEquals("13A records nothing; audio capture is Commit 13B", emptyList<String>(), offenders)
    }

    @Test
    fun `no internal engine name appears anywhere in sources or resources`() {
        // The public product rule, applied to the client: users see
        // IntelliAI (later IntelliAI STT) — never an engine name.
        val offenders = mainSources.walkTopDown()
            .filter { it.isFile && (it.extension == "kt" || it.extension == "xml") }
            .filter { it.readText().contains("whisper", ignoreCase = true) }
            .map { it.name }
            .toList()
        assertEquals(emptyList<String>(), offenders)
    }

    @Test
    fun `main sources exist where the build expects them`() {
        assertTrue(File(mainSources, "AndroidManifest.xml").isFile)
        assertTrue(File(mainSources, "java/com/intelliai/keyboard").isDirectory)
    }
}
