# Milestone 41 — TTS Product UI Status Update

| | |
|---|---|
| **Status** | COMPLETE — the console now tells the M40 truth: TTS is a real, usable Preview on the staging deployment, and still honestly "Coming Soon" on any production deployment, from the SAME static files |
| **Date** | 2026-08-24 |
| **Scope** | UI/product-status only. Zero backend behavior changes: no routing, no catalog, no billing, no contract, no promotion. |

    AI SERVICES UPDATED: YES
    API KEYS UPDATED: YES
    HOME UPDATED: YES
    SPEECH STUDIO LINK VERIFIED: YES
    PRODUCTION ROUTING CHANGED: NO
    HOSTINGER DEPLOYED: NO

    FINAL CLASSIFICATION: A — UI ACCURATELY REFLECTS CURRENT TTS STATUS

> **Superseded in part by M42 (2026-08-24).** This milestone was correct for its moment: TTS was implemented and staging-verified but NOT production-approved, so the badge distinguished deployments (Preview on a local/staging box, Coming Soon on production). The M42 promotion made TTS an approved production service, which created two meanings in one badge row — the STT card had said **Production** on the same undeployed box since M31 under the documented law *"launched as a product-grade offering, NOT a claim about which infrastructure hosts it"*. The founder chose one law for every service: the badge now follows the DEPLOYMENT'S CATALOG (`production` when it serves the service, `soon` when it does not), and the environment changes nothing. The mechanism this milestone built — `/console/status`, `withStatus()`, `badgeFor()`, production-safe static defaults — is unchanged and still in use; only the mapping moved. See [M42 §9](42-tts-production-promotion.md).

## 1. The architecture — status flows from the registry, never a string

The spec's preferred shape, implemented exactly:

    registry (the deployment's own catalog)
      ↓  GET /console/status          (new, unauthenticated, product facts only)
    IntelliAI.withStatus()            (applies the deployment's truth to the catalogue)
      ↓
    IntelliAI.badgeFor()              (ONE place decides badge text/style)
      ↓
    Home · AI Services · API Keys     (all render the same vocabulary)

- **`GET /console/status`** (pages.py): TTS is `"preview"` exactly when
  THIS deployment's registry serves the Hindi TTS route — which only
  the staging profile composes (the M39/M40 proposal). Languages come
  from the registry's voice records (`["en"]` production, `["en","hi"]`
  staging). No engines, no artifacts, no internal names in the payload
  (test-pinned).
- **The static files stay PRODUCTION-SAFE**: the catalogue entry ships
  `status: "soon"`, the API Keys page ships TTS in the Coming Soon
  list with a HIDDEN Preview chip. A fetch failure changes nothing —
  the console can never claim more than the deployment proves.

## 2. Status semantics (Phase 6) — documented at the source

| Badge | Meaning | Today |
|---|---|---|
| Production (`badge-live`) | serving production users | STT |
| Preview (`badge-beta`) | implemented + verified on THIS deployment; production not enabled | TTS on staging |
| Coming Soon (`badge-soon`) | not yet available to try | TTS on production; OCR/Translate/Vision/LLM everywhere |

The M31 "badge is a LAUNCH claim, not an infrastructure claim" law is
preserved; the old binary ternary in two renderers became the shared
three-state `badgeFor()` — the semantics pin was updated to guard the
new single source instead.

## 3. Page changes (before → after, staging)

- **AI Services**: TTS card "Coming Soon" → **Preview** badge
  (existing `badge-beta` styling), description "Natural speech from
  text with English and Hindi voices, streaming playback, and local
  preview access.", **Languages: English, Hindi** chips, and actions
  **Open Speech Studio** (primary) + View API Documentation — the same
  action row the STT card uses. STT card untouched (Phase 2).
- **Home** (Explore grid): TTS "Coming Soon" → **Preview**, same
  catalogue entry, "Open Speech Studio →" link unchanged.
- **API Keys**: "IntelliAI TTS, OCR, … — Coming Soon" → the
  **`IntelliAI TTS · Preview` chip** appears beside the STT chip and
  TTS drops out of the Coming Soon sentence. Same key, no new access
  rules — the backend already authorized TTS wherever it serves
  (Phase 4: nothing was changed to make the UI "look right").
- **Speech Studio**: already carried "IntelliAI TTS · Preview" (M35)
  and the catalog-driven voice dropdown (M39) — no change needed; all
  three entry points resolve to the existing `/console/speech`.
- **On a production deployment all four pages render exactly as
  before this milestone** — that is the point.

## 4. Verification

- **Live (staging, HTTPS edge)**: `/console/status` returns
  `{"tts":{"status":"preview","languages":["en","hi"]}}`; all pages
  carry the withStatus/badgeFor markers; the keys page ships the
  hidden chip; leak scan across home/services/keys/speech/console.js:
  **zero** hf_alpha / hm_psi / kokoro / espeak / misaki.
- **Tests**: 5 new pins (`TestM41LaunchStatus`) — production profile
  reports `soon` + `["en"]`, staging reports `preview` + `["en","hi"]`,
  the payload carries no engine vocabulary, the keys page defaults are
  production-safe, and no page hardcodes a `"Preview"` literal (badge
  text must come from the model). Console suite 35 green; api 676;
  tts-runtime 170; ruff/format/mypy strict clean. No guard weakened —
  the M31 badge-semantics pin was strengthened to the shared model.
- **Production safety (Phase 16)**: the diff touches five console
  files + pages.py + tests only; prod.yml, registry catalog,
  proposals, runtime, billing — zero diffs (`git diff` verified).

## 5. Limitations

- Server-side curls cannot execute the JS badge swap; the render path
  is covered by the unit pins + the live status endpoint + the
  founder's browser refresh (Ctrl+F5 — assets are no-cache, so the
  new shell loads immediately).
- When the TTS production launch eventually happens, `/console/status`
  gains its "production" case in the SAME commit as the launch gate —
  the endpoint is deliberately the one place that decision lands.
