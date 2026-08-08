# apps/keyboard-android — IntelliAI Keyboard

The first external client of the IntelliAI Platform: a real Android
input method (IME) built on `InputMethodService`.

**Current capabilities (Commit 13E):** installable keyboard,
enable/select onboarding, QWERTY typing through the real
`InputConnection`, **voice dictation** — tap the microphone, speak, and
IntelliAI STT's transcript is inserted into whatever app you're typing
in — **dictation language selection** (Auto / English / Hindi / Arabic),
an honest **Improve IntelliAI STT** contribution toggle, a
**correction** flow for collected dictations, and a hardened
**release configuration** (HTTPS-only, guarded against development
endpoints, unsigned-release built by CI on every change). IntelliAI
branding throughout; no internal engine names ever shown.

Dictation language maps to the API as: Auto → the `language` field is
omitted (the server detects it); English → `en`; Hindi → `hi`; Arabic →
`ar`. The choice is locked when a dictation starts, so changing it
mid-request never affects the request already in flight. Selecting
Arabic sets the dictation language only — it does not change the typing
layout (still QWERTY).

**Improve IntelliAI STT (contribution).** Settings has an *Improve
IntelliAI STT* toggle (on by default). When off, dictations send
`X-IntelliAI-Contribution: off` and the backend collects no training
sample for that request — an honest opt-out, not a cosmetic switch. The
organization's data consent remains the real ceiling, enforced
server-side: turning the toggle *on* can never opt in beyond what the
organization consented to. The choice is captured at dictation start,
like the language.

**Correction.** When a dictation is actually collected (contribution on
*and* org consent on), the backend returns a sample id and the keyboard
offers "Improve this transcription? · Edit". Editing opens a small
dialog prefilled with the transcript; saving sends the corrected text
verbatim to `POST /v1/audio/transcriptions/{id}/correction`. The
server keeps `original_transcript` immutable and updates
`current_transcript`. The correction updates the IntelliAI sample only —
it does **not** change the text already inserted in the host app. When
no sample was collected, no correction is offered (there is nothing to
correct). Correction state is held in memory and dropped when the field
changes.

**Boundary (permanent):** the keyboard is a client. It consumes the
IntelliAI platform exclusively through the public HTTPS API
(`POST /v1/audio/transcriptions`) and never touches PostgreSQL, object
storage, internal Python modules, or model runtimes. Every request
identifies itself with `X-IntelliAI-Client: keyboard/1.0`.

## One backend, two clients

The Web STT Studio and this keyboard are two clients of the **same**
IntelliAI backend — same `POST /v1/audio/transcriptions`, same
`model=intelliai-stt`, same Bearer-key authentication, same
omit-language-for-Auto semantics, same error envelope
(branch on `error.type`, never on raw HTTP status), same
`X-IntelliAI-Sample` collection signal, same correction endpoint. The
only intended differences are provenance (`X-IntelliAI-Client: web` vs
`keyboard/1.0`), UX, and how audio is captured.
`WebKeyboardContractTest` pins this in code: if it fails, keep the
clients identical — never fork the STT pipeline into an Android path.

## Build

```
make keyboard-apk        # debug APK, from the repository root
# or
cd apps/keyboard-android && ./gradlew assembleDebug
```

Requires JDK 17 and an Android SDK (`local.properties` with `sdk.dir`,
or `ANDROID_HOME`). Output: `app/build/outputs/apk/debug/app-debug.apk`.

### Release build

```
cd apps/keyboard-android && ./gradlew assembleRelease
```

Without signing material this produces
`app/build/outputs/apk/release/app-release-unsigned.apk` — CI builds
exactly this on every keyboard change, so a release-only compile
regression can never land unnoticed.

To produce a **signed** release, create `keystore.properties` next to
`settings.gradle.kts` (gitignored — signing material must never enter
git) with:

```
storeFile=/absolute/path/to/intelliai-release.jks
storePassword=…
keyAlias=intelliai-keyboard
keyPassword=…
```

and re-run `assembleRelease`. For a Play-Store bundle, `./gradlew
bundleRelease` produces an `.aab` with the same signing rules. Generate
the keystore once with `keytool -genkeypair -v -keystore
intelliai-release.jks -alias intelliai-keyboard -keyalg RSA -keysize
2048 -validity 10000` and keep it out of the repository.

## Test

```
make keyboard-test       # unit tests + Android lint
```

Unit tests cover the WAV container format, the STT API client (request
shape, headers, the full error-envelope matrix, secret hygiene) against
an OkHttp `MockWebServer`, the dictation state machine on virtual time,
the Web↔Keyboard backend contract, the release-configuration guards
(`ReleaseConfigGuardsTest` runs against the release variant's
`BuildConfig` in CI), and scope guards that keep out-of-scope
capabilities out of the build. See `RELEASE.md` for the physical-device
test checklist.

## Configure and use

1. Install the APK and open **IntelliAI**.
2. **Enable Keyboard**, then **Select Keyboard**.
3. Under **IntelliAI API**, paste an API key from the IntelliAI Console
   (`ik_live_…`) and **Save**. The key is stored in
   `EncryptedSharedPreferences` (Android Keystore-backed) and is never
   shown in full again, logged, or put in a screenshot.
4. Set the **API Server**. Debug builds default to `http://10.0.2.2:8000`
   (the Android emulator's route to a local IntelliAI stack). Release
   builds require an `https://` address to a real host — cleartext and
   development hosts (`10.0.2.2`, `localhost`, `127.0.0.1`) are refused
   at save time AND by the API client itself.
5. In any text field, tap the **microphone**, allow the mic permission
   when asked, speak, then tap **stop**. The transcript is inserted at
   the cursor.

### Debug vs release

- **Debug:** cleartext HTTP is permitted, but only to `10.0.2.2` (a
  scoped network-security config that release builds never merge), and
  the default server address is the emulator loopback.
- **Release:** HTTPS only, enforced three times over — the OS
  network-security default (no cleartext config is merged), the
  settings screen (rejects unsafe addresses at entry), and the API
  client (refuses to send a request to a cleartext or development
  address, with an honest error). No production domain is hardcoded —
  the server address is a deliberate configuration, and the compiled-in
  default is empty (`ReleaseConfigGuardsTest` pins all of this, and CI
  runs it against the release variant).

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
