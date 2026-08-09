# Cohort Onboarding — friendly-user wave

One organization **per household/person** (consent is org-level: individually grantable, individually revocable, one leaked key never exposes anyone else).

**One key per human (14A identity convention).** `speech_samples.user_identifier` records the acting key, so when every person has their own key, a person's deletion request maps exactly onto `make erase-user-data org=org_... user=key_...`. For a multi-person household org, create one additional key per speaker (`POST /v1/api-keys`, or re-run key creation in the console) instead of sharing one — shared keys make per-person erasure impossible below the key's granularity (docs/DATA_GOVERNANCE.md).

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
`make revoke-consent org=org_...` stops collection immediately. Deleting already-stored data is a first-class verb now (14A):

```bash
make erase-user-data org=org_... user=key_...   # one person's samples
make erase-org org=org_...                      # the whole tenant's data
```

Objects first, rows second, usage ledger retained, manifests containing the erased voice revoked loudly — the full policy is docs/DATA_GOVERNANCE.md. Both requests are honored without question — that's the deal that makes the data clean.
