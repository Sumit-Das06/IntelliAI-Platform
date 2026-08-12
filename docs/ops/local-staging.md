# Local Staging — drive the Hindi→Qwen flow yourself

> The full customer pipeline, on your machine, with the proposed routing
> live: **Web STT Studio → `/v1/audio/transcriptions` → auth → gateway →
> language routing → (hi → Qwen3-ASR 0.6B | other → Whisper-small) →
> transcript → usage ledger → optional collection → correction.**
>
> Production posture is untouched by construction: the staging profile
> lives only in `infra/compose/local-staging.yml`, is applied only by the
> explicit `staging-*` targets below, is refused under `INTELLIAI_ENV=prod`
> by a settings validator, and guard tests pin that no production file
> references any of it.

## 1. Start it

```
make staging-seed-models   # optional: copies local GGUFs into the volume
                           # (skip = first boot downloads ~1 GB, hash-verified)
make staging-up            # builds images (vendored llama.cpp layer) + starts
make ps                    # wait until api and stt-runtime report healthy
```

First boot is the slowest (image build + model verify). The stt-runtime
healthcheck allows up to 10 minutes; subsequent boots are seconds.

## 2. Mint yourself an API key

```
make bootstrap-org org="My Staging Org" email="you@example.com" name="You"
```

Copy the printed `ik_live_…` key (shown once). To also test speech-sample
collection, grant consent for the printed `org_…` id:

```
docker compose exec api python -m intelliai_api.cli grant-consent \
  --org <org_...> --reference "local-staging-consent"
```

## 3. Web STT Studio

1. Open **http://localhost:8000/console/playground**, paste your key.
2. Language **Hindi** → record or upload Hindi speech → **Transcribe**.
   - Open **Developer details**: request ID, sample ID, raw response.
   - Edit the transcript → **Save correction**.
   - Untick **Contribute** → transcribe again → sample shows *not stored*.
3. Language **English** → transcribe an English clip.
4. **See which model served each request** (the UI deliberately never says):
   ```
   docker compose logs stt-runtime | grep transcription_completed
   ```
   Hindi requests show `"artifact": "qwen3-asr-0.6b"`, English/default
   `"artifact": "whisper-small"`.
5. Usage: **http://localhost:8000/console/usage** — every successful
   request metered once, refusals not billed.
6. Limits: audio over **120 s** on Hindi is refused with a clear message
   (the measured-safe ceiling of the candidate at ctx 4096).

## 4. Android keyboard (optional, needs your phone)

The debug APK's server address must reach your machine:

- **USB (recommended):** `adb reverse tcp:8000 tcp:8000`, then set the
  keyboard's server address to `http://127.0.0.1:8000`.
- **LAN:** the stack binds loopback-only on purpose. If you accept LAN
  exposure on your own network, add a port override yourself and set
  `http://<your-laptop-ip>:8000`.

Then: pick Hindi, dictate, watch the transcript land in the focused app;
toggle Contribution in the keyboard settings and compare sample behavior.

## 5. What "unchanged production" means here

- `make prod-up` composes base + `infra/compose/prod.yml` only — Hindi
  resolves to **whisper-small** there, test-pinned.
- The staging gateway logs `registry_profile_staging` loudly at boot.

## 6. Back to normal

```
make staging-down   # stop the staging shape (data volumes preserved)
make up             # normal dev stack: hi→whisper, single-slot runtime
```

Data written during staging (usage events, samples) stays in your local
Postgres/MinIO volumes — it is ordinary tenant data under your staging org.
