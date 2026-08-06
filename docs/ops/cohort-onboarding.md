# Cohort Onboarding — friendly-user wave

One organization **per household/person** (consent is org-level: individually grantable, individually revocable, one leaked key never exposes anyone else).

## Per member
```bash
make bootstrap-org org="Sharma Household" email="unique@example.com" name="Asha"
# → prints org_... and the API key ONCE. Put the key straight into a
#   password-manager share for that person. Never chat/email it in plaintext.
make grant-consent org=org_... ref="cohort-2026-08-consent-v1"
```
`ref` names the signed consent document version. **Consent form signed BEFORE the grant** — the reference is the paper trail. Product works fine without consent (transcription only, nothing stored) — consent-off members are welcome too.

## What they get
- `https://$DOMAIN/playground` — works in any phone browser. Paste key once → Record → Transcribe → fix the text → Save correction.
- Ask them to speak **naturally** in whatever language they actually use (Hinglish very much included), and to fix transcripts when they have 10 seconds — corrections are the most valuable thing they can give.
- Set expectations honestly: **Hindi and Arabic are beta** — imperfect output is expected and is exactly what their usage improves.

## Rules that protect the data
- Nothing sensitive: no real phone numbers, addresses, or other people's private details in recordings.
- Don't record other people without permission (the page says so permanently).
- **Speaker separation law:** anyone who records for the *evaluation corpus* (the Hindi corpus project) must NOT be a cohort user, and vice versa — the wall between training and evaluation includes voices. Keep one list of who is on which side.

## Off-boarding / deletion
`make revoke-consent org=org_...` stops collection immediately; deletion of already-stored samples is the runbook's operator procedure. Both are honored without question — that's the deal that makes the data clean.
