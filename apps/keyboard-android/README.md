# apps/keyboard-android — IntelliAI Keyboard

The first external client of the IntelliAI Platform: a real Android
input method (IME) built on `InputMethodService`.

**Current capabilities (Commit 13C):** installable keyboard,
enable/select onboarding, QWERTY typing through the real
`InputConnection`, **voice dictation** — tap the microphone, speak, and
IntelliAI STT's transcript is inserted into whatever app you're typing
in — and **dictation language selection** (Auto / English / Hindi /
Arabic) from a chip on the keyboard or from Settings. IntelliAI
branding throughout; no internal engine names ever shown.

Dictation language maps to the API as: Auto → the `language` field is
omitted (the server detects it); English → `en`; Hindi → `hi`; Arabic →
`ar`. The choice is locked when a dictation starts, so changing it
mid-request never affects the request already in flight. Selecting
Arabic sets the dictation language only — it does not change the typing
layout (still QWERTY).

**Not yet implemented:** a contribution toggle ("Improve IntelliAI STT")
and transcript-correction UI are deliberately deferred to later commits.
Today, whether a dictation becomes a training sample is decided entirely
by your organization's existing consent setting on the platform — the
keyboard sends no contribution or correction signals of its own.

**Boundary (permanent):** the keyboard is a client. It consumes the
IntelliAI platform exclusively through the public HTTPS API
(`POST /v1/audio/transcriptions`) and never touches PostgreSQL, object
storage, internal Python modules, or model runtimes. Every request
identifies itself with `X-IntelliAI-Client: keyboard/1.0`.

## Build

```
make keyboard-apk        # from the repository root
# or
cd apps/keyboard-android && ./gradlew assembleDebug
```

Requires JDK 17 and an Android SDK (`local.properties` with `sdk.dir`,
or `ANDROID_HOME`). Output: `app/build/outputs/apk/debug/app-debug.apk`.

## Test

```
make keyboard-test       # unit tests + Android lint
```

Unit tests cover the WAV container format, the STT API client (request
shape, headers, the full error-envelope matrix, secret hygiene) against
an OkHttp `MockWebServer`, the dictation state machine on virtual time,
and scope guards that keep out-of-scope capabilities out of the build.

## Configure and use

1. Install the APK and open **IntelliAI**.
2. **Enable Keyboard**, then **Select Keyboard**.
3. Under **IntelliAI API**, paste an API key from the IntelliAI Console
   (`ik_live_…`) and **Save**. The key is stored in
   `EncryptedSharedPreferences` (Android Keystore-backed) and is never
   shown in full again, logged, or put in a screenshot.
4. Set the **API Server**. Debug builds default to `http://10.0.2.2:8000`
   (the Android emulator's route to a local IntelliAI stack). Release
   builds require an `https://` address — cleartext is refused.
5. In any text field, tap the **microphone**, allow the mic permission
   when asked, speak, then tap **stop**. The transcript is inserted at
   the cursor.

### Debug vs release

- **Debug:** cleartext HTTP is permitted, but only to `10.0.2.2` (a
  scoped network-security config that release builds never merge).
- **Release:** HTTPS only. No production domain is hardcoded — the
  server address is a deliberate configuration.

## Permissions & privacy

Two permissions, each earned by dictation: `RECORD_AUDIO` and
`INTERNET`. The microphone is captured only between an explicit tap and
stop; recordings live only in memory (never written to disk) and are
sent only to the configured IntelliAI API, then dropped. Recordings cap
at 60 seconds. Nothing you type is logged, stored, or transmitted — the
keyboard has no `android.util.Log` calls at all. The mic-permission
dialog is requested through a transparent trampoline activity, because
an `InputMethodService` cannot host that dialog itself; denial is
handled gracefully with an honest message.
