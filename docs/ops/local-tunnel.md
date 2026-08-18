# Local HTTPS + Cloudflare Tunnel — test Web & Android against the E3 stack

> The exact backend we intend to deploy later, running locally, reachable
> by the real Web console and the real Android keyboard over HTTPS:
>
> ```
> Internet → Cloudflare Tunnel → Caddy (local HTTPS edge) → API
>                                      → STT runtime (hi → Qwen E3, en → Whisper)
>                                      → Postgres / Redis / MinIO (private)
> ```
>
> Only Caddy is reachable through the tunnel. Postgres, Redis, MinIO and
> the STT runtime stay on loopback/container networks — the tunnel
> forwards exactly one origin.

## 1. Start the local production-shaped stack

```
make local-prod-check    # preflight (same battery as prod-check)
make local-prod-up       # seeds models (E3 cannot be downloaded) + starts
make local-prod-migrate  # first time only
make local-prod-health
make local-prod-smoke    # same battery as prod-smoke
```

Hindi now routes to `qwen3-asr-0.6b-hi-ft-e3`; English and default stay
on whisper-small. Production (`make prod-up`) is untouched: it cannot
serve E3 — the settings layer refuses the staging registry profile under
`INTELLIAI_ENV=prod`, and guard tests pin it.

## 2. Start the tunnel (no account, no credentials, no DNS)

A Cloudflare **quick tunnel** needs nothing from you — no token, no
account, no domain. Install `cloudflared` once
(https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/
— on Windows: `winget install Cloudflare.cloudflared`), then:

```
cloudflared tunnel --url https://localhost:443 --no-tls-verify
```

- `--url https://localhost:443` targets the CADDY EDGE, so every request
  passes the same TLS termination, security headers, and 30 MB body
  ceiling production will apply.
- `--no-tls-verify` accepts Caddy's self-signed localhost certificate on
  the LOCAL hop only; clients on the internet see a REAL Cloudflare
  certificate for the tunnel hostname.
- cloudflared prints a line like:

  ```
  https://random-words-here.trycloudflare.com
  ```

  **That URL is your tunnel address.** It changes on every start; nothing
  is committed anywhere, nothing persists, closing cloudflared closes the
  door. Do NOT put it in any committed file.

## 3. Web through the tunnel

Open `https://<your-tunnel>.trycloudflare.com/console/playground` in any
browser (any device, any network). The console is served by the gateway
itself, so there is no separate Web origin and no CORS involved —
everything is same-origin behind the tunnel. Paste your API key
(`make bootstrap-org …` mints one) and test exactly as in
docs/ops/local-staging.md §3.

## 4. Android through the tunnel

The keyboard's server address is a **runtime setting**, not a build
value — no APK change, and never touch the release configuration:

1. Install/keep the existing debug APK.
2. Keyboard settings → server address →
   `https://<your-tunnel>.trycloudflare.com`
3. Paste the API key, pick Hindi, dictate.

The backend accepts up to 600 s of audio, but the Android HTTP call cap
(150 s) is shorter than long-audio walls — Hindi clips beyond roughly
120 s may hit the CLIENT timeout even though the backend succeeds.
Documented limitation; raising the client timeout is its own future
milestone. Web has no such cap and can exercise 300 s / 600 s fully.

## 4b. Measured limits of the quick tunnel (M25 evidence)

The Cloudflare edge holds a response open for roughly 100 seconds on
quick tunnels. Measured consequences (tunnel-gateway-drills.json):

- **≤300 s audio: fully works through the tunnel** (a 300 s clip
  returned complete in ~84 s wall).
- **600 s audio: the EDGE aborts with 524** after ~100 s while the
  request is still decoding. The backend then cancels cleanly — **no
  partial transcript, zero billing** (the M19 whole-request law,
  re-proven through a real internet edge). Verify 600 s against the
  local edge instead (`https://localhost`, self-signed) — it completes
  there (~196 s, 7 segments).
- Android's own 150 s call cap binds before the tunnel's on long audio
  anyway; Web through the tunnel is the 300 s-class test surface.

A future Hostinger deployment has no Cloudflare proxy in front (Caddy
terminates TLS directly), so this cap is a property of the TEST path
only.

## 5. Troubleshooting

| Symptom | Check |
|---|---|
| tunnel URL 502/530 | Is the stack up? `make local-prod-health`; is Caddy on 443? `docker compose ps caddy` |
| tunnel URL times out | cloudflared still running? It must stay in the foreground (or use a second terminal) |
| browser warns about certificate | You opened `https://localhost` directly (self-signed) — that warning is expected locally; the tunnel URL carries a valid certificate |
| 401 from the console | Key pasted wrong, or the org was created against a different database volume |
| Hindi serves whisper | The stack is running the plain dev/staging shape — `make local-prod-up`, then check `docker compose logs stt-runtime | grep transcription_completed` |
| slow first Hindi request | first llama-server spawn + model map; subsequent requests are warm |

## 6. Stop everything

```
Ctrl-C the cloudflared process   # closes the public URL immediately
make local-prod-down             # stops the stack (volumes kept)
make up                          # back to the normal dev shape
```
