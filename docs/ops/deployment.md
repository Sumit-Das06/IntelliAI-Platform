# Deployment Guide — IntelliAI STT v1

One VPS, Docker Compose, HTTPS via Caddy. ~30 minutes from blank machine to serving.

## Prerequisites
- A VPS: 8 vCPU / 16 GB RAM class, Ubuntu 22.04+, ports 80+443 open.
  **Pick the region deliberately** — data residency is a product fact (India-first cohort → an Indian region).
- A domain/subdomain (e.g. `api.yourdomain.com`) with an **A record → VPS IP**, created *before* first start (Caddy needs it for Let's Encrypt).
- Docker Engine + Compose plugin installed (`curl -fsSL https://get.docker.com | sh`).

## Steps
```bash
git clone <repo> /opt/intelliai && cd /opt/intelliai
cp .env.prod.example .env        # then EDIT: domain + three generated secrets
make prod-up                     # builds images, starts caddy+api+stt+pg+redis+minio
make prod-migrate                # apply database migrations
```
First start downloads whisper (~480 MB, hash-verified) into the model volume; the stt healthcheck allows up to 10 minutes for it.

## Verify
```bash
curl -s https://$DOMAIN/health/ready          # every check "ok"
open https://$DOMAIN/playground               # the mini console renders
```
Then create the first org + consent (see `cohort-onboarding.md`) and dictate once end-to-end.

## After deploy (same day, not optional)
1. **Uptime monitor**: external ping on `https://$DOMAIN/health/ready` (UptimeRobot/healthchecks.io class), alert to your phone.
2. **Backups**: install the cron line from `backup.md`, run one backup, **do one restore drill**.
3. Store `.env` secrets in your password manager; the file never leaves the box.

## Updating
```bash
cd /opt/intelliai && git pull && make prod-up && make prod-migrate
```
Compose rebuilds and restarts only what changed. TTS stays off (compose profile) until its version arrives.
