# IntelliAI Keyboard — MVP Release Readiness (Commit 13E)

This document is the release operator's guide: how the artifacts are
built, what is verified by machines, and exactly what a human must
verify on a physical phone before any public release.

**Verification status, honestly stated:**

| Surface | Status |
| --- | --- |
| Unit tests (debug + release variants), lint (both), scope + release-config guards | ✅ CI, every change |
| Debug APK + unsigned release APK compile | ✅ CI, every change |
| End-to-end against the real IntelliAI stack (dictation, languages, contribution, correction, provenance) | ✅ Android 15 **emulator** |
| Physical Android phone | ⏳ **PENDING — never claimed. Use the checklist below.** |

## Build artifacts

- **Debug:** `./gradlew assembleDebug` →
  `app/build/outputs/apk/debug/app-debug.apk`. Defaults to the emulator
  loopback server (`http://10.0.2.2:8000`); cleartext allowed to that
  single host only.
- **Release (unsigned):** `./gradlew assembleRelease` →
  `app/build/outputs/apk/release/app-release-unsigned.apk`. HTTPS-only,
  empty default server address, no debug network config merged. CI
  uploads both APKs as build artifacts on every keyboard change.
- **Release (signed):** supply `keystore.properties` (see README
  "Release build") and re-run `assembleRelease`, or `bundleRelease` for
  an `.aab`. The keystore and its properties file are gitignored;
  nothing in this repository can sign a release, deliberately.

Reproducibility: the Gradle wrapper pins the build tooling
(Gradle 8.10.2 / AGP 8.7.3 / Kotlin 2.0.21 via `gradle/libs.versions.toml`),
`versionCode`/`versionName` live in `app/build.gradle.kts` only, and the
About line renders `BuildConfig.VERSION_NAME` so the displayed version
cannot drift from the build.

## Install (debug, for testing)

```
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

Then: open **IntelliAI** → Enable Keyboard → Select Keyboard → paste an
`ik_live_…` key → set the API Server → dictate in any app.

## Physical-device test checklist

No physical Android phone was available in the 13E environment, so the
items below are **not** covered by any automated or emulator result.
Run them on at least one real phone (ideally one recent Pixel/Samsung
and one budget device) before public release. Check items off in a copy
of this list and record device model + Android version.

### Setup & onboarding
- [ ] APK installs cleanly (debug via adb; release via signed build)
- [ ] Onboarding: Enable Keyboard opens system settings; IntelliAI appears in the keyboard list
- [ ] Select Keyboard shows the system picker; IntelliAI becomes the active IME
- [ ] Status lines flip to ✓ immediately on returning to the app
- [ ] API key saves; status shows only the `ik_live_…xxxx` hint; the input field clears
- [ ] Release build refuses `http://` and `https://localhost` style addresses with the honest message

### Dictation (per language)
- [ ] English dictation into a plain text field inserts a correct transcript
- [ ] Hindi dictation by a Hindi speaker inserts Devanagari text *(do not claim quality from a non-native reading)*
- [ ] Arabic dictation by an Arabic speaker inserts Arabic text *(same honesty rule)*
- [ ] Auto mode transcribes without a language being sent
- [ ] Changing language mid-recording does not affect the in-flight request; the next request uses the new language

### Real apps
- [ ] WhatsApp message field: type, dictate, send
- [ ] Chrome address/search bar: dictation + the action key performs Search/Go
- [ ] Gmail compose (subject = single-line, body = multiline): dictation + Enter behavior correct in each
- [ ] Contacts name field: dictation capitalizes sensibly, no crash on field switch
- [ ] Password fields: keyboard types normally (and nothing is ever logged)

### Contribution & correction
- [ ] Contribution ON + org consent ON → dictation produces a sample (Console → Speech Samples shows it, `client_source=keyboard`)
- [ ] Contribution OFF → dictation works, NO sample appears
- [ ] Org consent OFF + contribution ON → NO sample appears (the ceiling holds)
- [ ] Collected dictation shows "Improve this transcription?"; Edit → correct → save → Console shows original preserved + corrected current transcript
- [ ] Non-collected dictation never shows the correction offer

### Reliability on real hardware
- [ ] Airplane mode: dictation fails with the honest network message; keyboard stays usable
- [ ] Kill Wi-Fi mid-upload: error surfaces, keyboard returns to idle
- [ ] Invalid/revoked API key: honest message, no crash
- [ ] 60-second cap: recording auto-stops and still transcribes
- [ ] Rapid repeated mic taps: no double-recording, no stuck state
- [ ] Mic permission denied → honest message; grant later via Settings → dictation works
- [ ] Revoke mic permission while the app is installed → next dictation re-asks, no crash

### Lifecycle on real hardware
- [ ] Screen rotation while the keyboard is open (and while recording): no crash; recording stops safely
- [ ] Switch apps mid-processing: no crash; no text typed into the wrong app
- [ ] Keyboard hidden while recording: microphone released immediately (indicator dot disappears)
- [ ] Globe key switches to another keyboard and back
- [ ] Reboot phone: API key, language, and contribution settings survive; keyboard still selected

### Privacy spot-checks
- [ ] `adb logcat` during a full dictation+correction session contains no API key, no transcript, no audio bytes
- [ ] `adb shell run-as com.intelliai.keyboard ls -R files/ cache/` (debug build) shows no audio files
- [ ] Battery/data usage for the keyboard looks proportionate (no background traffic)

## Play Store requirements (14A inventory — nothing published yet)

What the developer must have in hand before an upload; none of it is
generated by this repository:

- **Play Console account** ($25 one-time). New personal accounts may
  face a closed-testing requirement before production access — check
  current policy when planning the date.
- **Signed AAB**: `./gradlew bundleRelease` with `keystore.properties`
  supplied (see "Release build" in README). Keystore backed up in two
  places; losing it means never updating the app again.
- **Privacy policy URL** — must exist and match actual behavior; source
  material: `docs/legal/PRIVACY_DISCLOSURES.md` (draft, needs counsel).
- **Data Safety form** — our honest mapping:
  - *Audio* — collected **optionally** (user can dictate without
    contributing: contribution toggle off, or org consent absent);
    purpose: app functionality (transcription), and app improvement
    (only with org consent AND contribution on). Not shared with third
    parties. User can request deletion (erasure verbs exist server-side,
    `docs/DATA_GOVERNANCE.md`).
  - *Personal identifiers* — none collected by the keyboard itself; the
    API key identifies the organization/person under the pilot's
    one-key-per-person convention.
  - *Typed text* — never collected, never transmitted.
- **Microphone permission disclosure** — captured only between explicit
  tap and stop, 60 s cap, in-memory only, sent solely to the configured
  IntelliAI server.
- **Listing assets** — icon (exists), feature graphic, screenshots,
  short/long description (public product language only: IntelliAI STT,
  never engine names).
- **Production API domain** baked in as the release default before the
  build that ships (deliberately absent today).

## What 13E deliberately does NOT include

No fine-tuning, training executor, GPU infrastructure, evaluation
pipeline, model promotion/deployment, no new STT backend, and no
Android-specific STT path — those belong to the ML milestones. The
keyboard remains a pure client of `POST /v1/audio/transcriptions`.
