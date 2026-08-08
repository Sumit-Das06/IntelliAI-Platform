# apps/keyboard-android — IntelliAI Keyboard

The first external client of the IntelliAI Platform: a real Android
input method (IME) built on `InputMethodService`.

**Commit 13A scope (current):** installable keyboard, enable/select
onboarding, QWERTY typing through the real `InputConnection`, IntelliAI
branding, and an honest microphone placeholder. No audio recording, no
network calls, no permissions, no telemetry — this version does not
send anything you type anywhere.

**Boundary (permanent):** the keyboard is a client. It consumes the
IntelliAI platform exclusively through the public HTTPS API
(`POST /v1/audio/transcriptions`, arriving in Commit 13B) and never
touches PostgreSQL, object storage, internal Python modules, or model
runtimes. It identifies itself with `X-IntelliAI-Client: keyboard/1.0`.

## Build

```
make keyboard-apk        # from the repository root
# or
cd apps/keyboard-android && ./gradlew assembleDebug
```

Requires JDK 17 and an Android SDK (`local.properties` with `sdk.dir`,
or `ANDROID_HOME`). Output: `app/build/outputs/apk/debug/app-debug.apk`.

## Try it

1. Install the APK and open **IntelliAI**.
2. **Enable Keyboard** → toggles IntelliAI on in Android's keyboard list.
3. **Select Keyboard** → choose IntelliAI as the active input method.
4. Type in the built-in test field — or any app.

The mic button shows "Voice typing with IntelliAI STT is coming next."
— dictation is Commit 13B, and this version makes no claim otherwise.
