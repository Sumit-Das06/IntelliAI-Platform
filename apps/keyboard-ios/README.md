# IntelliAI iOS Keyboard

A native iOS custom keyboard that dictates through the **same public
IntelliAI backend** as Web and the Android keyboard — one endpoint,
one contract, no iOS-specific server surface:

```
iOS Keyboard ──► POST /v1/audio/transcriptions
                 Authorization: Bearer <key>
                 X-IntelliAI-Client: ios-keyboard/1.0
                 model=intelliai-stt  [language=en|hi|ar, omitted for Auto]
```

## Architecture

Two targets plus a shared layer (mirroring the Android app's shape):

| | Responsibilities |
|---|---|
| **IntelliAI** (container app) | Onboarding & keyboard enablement instructions · API-key entry into the **shared Keychain** (masked after save, removable) · server address · language & contribution settings · the **microphone permission grant** (an extension cannot present the prompt) · the correction editor |
| **IntelliAIKeyboard** (extension) | Key rows + mic key + language chip + status line · the dictation state machine · transcript insertion via `textDocumentProxy` · READS settings/key, never writes them |
| **Shared/** (both targets) | `IntelliAIApiClient` (URLSession; the Android client's laws verbatim) · `WavRecorder`/`WavEncoder` (AVAudioEngine → 16 kHz mono PCM16 RIFF) · `DictationController` (state machine) · `SettingsStore` (App Group) · `KeychainStore` (shared access group) · `DictationLanguage` · `ServerAddress` |

State sharing uses Apple's supported mechanisms and nothing else:
**App Group** (`group.com.intelliai.keyboard`) for non-secret settings,
**shared Keychain access group** for the API key. The key never touches
UserDefaults, files, logs, the clipboard, or shared text.

## Building (requires a Mac)

The `.xcodeproj` is generated, never committed:

```
brew install xcodegen
cd apps/keyboard-ios
xcodegen generate
open IntelliAIKeyboard.xcodeproj
```

Set your development team in the Signing pane (or pass
`DEVELOPMENT_TEAM=` to `xcodebuild`). Requirements: Xcode 15+,
iOS 16.0+ target. Tests: `⌘U` (the `IntelliAIKeyboardTests` bundle —
pure-seam tests, no entitlements needed).

## Using it

1. Build & run **IntelliAI** on the device.
2. In the app: save your API key (`ik_live_…`), set the server address
   (HTTPS; for local testing the Cloudflare tunnel URL from
   `docs/ops/local-tunnel.md`), allow the microphone.
3. Settings → General → Keyboard → Keyboards → **Add New Keyboard →
   IntelliAI**, then enable **Allow Full Access** (required for the
   network request; iOS shows its own warning — see Privacy below).
4. In any app: switch to the IntelliAI keyboard (globe), pick a
   language on the chip (Auto/EN/HI/AR), tap the mic, speak, tap again
   — the transcript lands at the cursor.

## Behavior contract (identical to Android)

- **Languages**: Auto omits the `language` field (server detects);
  English/Hindi/Arabic send `en`/`hi`/`ar`. Nothing else can ever be
  sent. Changing language mid-request never affects the in-flight
  request.
- **Contribution**: ON sends nothing extra (org consent remains the
  server-side ceiling); OFF sends `X-IntelliAI-Contribution: off`.
- **Correction**: when a dictation was collected (sample id returned),
  the container app offers *Improve this transcription* →
  `POST /v1/audio/transcriptions/{sample_id}/correction`. The original
  transcript stays immutable server-side.
- **Errors**: branched on the envelope's `error.type`, never on bare
  HTTP status; one bounded retry only for the 503 family; product-safe
  wording only (no internal engine or model names, ever).
- **Recording**: 16 kHz/mono/PCM16 WAV, 60 s cap (cap sends, never
  discards), interruptions (calls/Siri) stop-and-send, dismissing the
  keyboard cancels everything and inserts nothing.

## Privacy (what the keyboard can and cannot do)

- With Full Access OFF the keyboard can type but cannot dictate (no
  network) — it says so instead of failing opaquely.
- Audio goes directly into the request body; nothing is written to
  disk, and cancellation discards captured PCM.
- The API key is Keychain-only (`AfterFirstUnlock`), masked in UI after
  saving, excluded from unencrypted backups by construction.
- The keyboard never reads the clipboard, never logs typed text, and
  sends exactly one request per dictation.

## Known iOS limitations (honest list)

- **Microphone in extensions**: the permission prompt can only be
  granted in the container app; on some iOS versions keyboard
  extensions are restricted from `AVAudioSession` recording even with
  Full Access — REQUIRES DEVICE VERIFICATION. If a target iOS version
  refuses, the documented fallback is dictation via the container app
  with an App-Group handoff (not implemented until a device confirms
  the need).
- Restricted input contexts (secure text fields, some webviews) may
  refuse programmatic insertion — standard iOS behavior for all
  custom keyboards.
- Long audio: dictation is capped at 60 s client-side (matching
  Android); long-form audio remains a Web workflow.
- This project has **not yet been compiled** — it was authored on a
  non-Mac environment; the API contract was verified against the live
  backend with the exact request shapes, but `xcodegen + xcodebuild`
  verification is pending Mac access (see the M27 report).
