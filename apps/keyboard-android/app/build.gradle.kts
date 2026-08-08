plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
}

android {
    namespace = "com.intelliai.keyboard"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.intelliai.keyboard"
        minSdk = 26
        targetSdk = 35
        versionCode = 1
        versionName = "0.1.0"
    }

    buildTypes {
        // The API base URL is a per-build-type DEFAULT the user can
        // override in settings. Debug points at the emulator's host
        // loopback for local development; release ships with no default
        // at all — a production domain is a deliberate configuration,
        // never a hardcoded guess (the repo names none yet).
        debug {
            buildConfigField("String", "DEFAULT_BASE_URL", "\"http://10.0.2.2:8000\"")
        }
        release {
            buildConfigField("String", "DEFAULT_BASE_URL", "\"\"")
            // No shrinking yet: three small dependencies, and release
            // signing is a later, deliberate decision.
            isMinifyEnabled = false
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
        }
    }

    buildFeatures {
        buildConfig = true
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }
}

dependencies {
    // Deliberately minimal: an IME is the most trusted app class on a
    // phone, and every dependency is attack surface. Each addition
    // carries its justification; ScopeGuardsTest bans the heavyweights
    // (Retrofit, Volley, Ktor, WorkManager, analytics SDKs).
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.appcompat)
    implementation(libs.material)
    // OkHttp: the one multipart upload 13B needs — mature, small,
    // testable via MockWebServer. Retrofit would add codegen for a
    // single endpoint.
    implementation(libs.okhttp)
    // EncryptedSharedPreferences: the API key must never sit in
    // plaintext prefs; this is the AndroidX Keystore-backed answer.
    implementation(libs.androidx.security.crypto)
    // Coroutines: recording and upload must leave the IME thread, and
    // service destruction must be able to CANCEL in-flight work —
    // structured concurrency is the safe way to keep that promise.
    implementation(libs.coroutines.android)

    testImplementation(libs.junit)
    testImplementation(libs.mockwebserver)
    testImplementation(libs.coroutines.test)
    // The android.jar on the unit-test classpath stubs org.json; this
    // is the real implementation so envelope parsing is actually tested.
    testImplementation(libs.json)
}
