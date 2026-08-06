# Hindi Corpus Collection Guide v1

| | |
|---|---|
| **Status** | v1 — operational field manual. The rules come from the [Hindi Evaluation Corpus Specification v1](hindi-evaluation-corpus-spec.md), which this guide executes and never overrides. |
| **Who this is for** | Anyone helping collect recordings — no project knowledge required. If you only read one page, read §8 (the checklist). |
| **The one law** | Recordings are **real people speaking naturally, with signed consent, recorded by us**. Nothing from YouTube, TV, radio, WhatsApp forwards, or any existing recording. Ever. |

## 1. Collection Workflow

```
Recruit speaker ─► Consent signed & filed ─► Speaker briefed (§3)
      ─► Recording session (§3–§4) ─► Files named (§5) + metadata row (§6)
      ─► Upload to the staging folder (ml/evaluation/corpus-inbox/ — never
         committed to the repository; it is gitignored by design)
      ─► Quality review (§7): ACCEPT / REJECT per clip, reason logged
      ─► Accepted clips hashed and registered; metadata attached
      ─► Transcription (separate step, done by the transcription team
         under the convention sheet — collectors never transcribe)
      ─► Dataset inclusion at the next corpus release
```

A clip is not "in the corpus" until it passes review AND is transcribed AND a release includes it. Collectors are responsible up to the upload + metadata step.

## 2. Speaker Recruitment

- **Who:** adults (18+) who speak Hindi in daily life. Primarily **native Hindi speakers** (target ≥80% of speakers); fluent second-language Hindi speakers are welcome for the remainder and are tagged as such — real customers include them.
- **Diversity targets** (the spec's hard minima, restated for recruiters):
  - **≥12–15 speakers recruited** (the corpus needs ≥10 *accepted*; recruit extra — some recordings will be rejected).
  - **Gender:** roughly balanced — at least 5 men and 5 women among accepted speakers.
  - **Age:** spread across at least three bands (18–30, 31–45, 46+). Do not collect only from one friend circle of the same age.
  - **Region:** at least 3 distinct Hindi-belt backgrounds (e.g., Delhi/West UP, East UP/Bihar, MP/Rajasthan, Mumbai-influenced). Recruit where the speakers actually grew up speaking, not where they live now.
  - **Education/occupation:** mix them deliberately — students, office workers, shopkeepers, homemakers, retirees. Varied vocabulary is the point.
- **Volume per speaker:** target **8–12 clips each**; hard cap **15 clips** per speaker (no speaker may dominate the corpus). More speakers beats more clips per speaker, always.
- **Never recruit for the evaluation corpus anyone who may later record training audio** — the two rosters must stay disjoint. If unsure, ask before recording.

## 3. Recording Instructions

**Setup:**
- Any decent smartphone or laptop microphone is fine. Use a **lossless recorder app (WAV/FLAC)** if available; otherwise the phone's highest-quality setting. Never send recordings through WhatsApp/Telegram — messaging apps recompress audio. Transfer the original file.
- **Microphone distance: 15–30 cm** (a hand-span). Not touching the mouth, not across the room.
- Phone on Do Not Disturb. Remove the phone from its case if it muffles.

**How to speak:**
- **Naturally. This is the single most important instruction.** Speak as you would to a friend or on an ordinary phone call. Hesitations, "अं", "matlab", restarts, and mixed English words are all *wanted* — they are real speech.
- **No acting. No exaggerated clarity.** Do not slow down, over-articulate, or perform. If it sounds like a news anchor and the session isn't the formal category, it's wrong.
- **Do not read** unless the session is explicitly a reading session (≤30% of the corpus is read speech; the collector will tell you which type this session is).
- **Normal speed, normal volume.** If you stumble, keep going — do not restart the clip.

**Environments (the collector chooses per session, to fill the quotas):**
- **Indoor clean** (most sessions): quiet room, fan off if loud, TV/music OFF — background media is an automatic rejection.
- **Indoor noisy:** kitchen sounds, family in another room, café — real, incidental noise. Never *add* noise artificially.
- **Outdoor:** street, market, park. Wind is fine; shouting over traffic is not.
- **Telephony:** an actual phone call recorded with a call-recording setup (with both parties' consent) — genuine narrowband, not a simulation.

## 4. Recording Script Categories — prompts, not transcripts

Give the speaker a prompt and let them talk. Never hand them sentences to say (except designated reading sessions). One clip = one prompt, 15 seconds to 2 minutes.

**Conversation & daily life:** "आपका कल का दिन कैसा था? सुबह से बताइए।" · "अपने मोहल्ले के बारे में बताइए।" · "बारिश के मौसम में आपकी दिनचर्या कैसे बदलती है?"
**Storytelling:** "बचपन की कोई यादगार घटना सुनाइए।" · "कोई त्योहार कैसे मनाया था, पूरा किस्सा।"
**Directions:** "अपने घर से नज़दीकी बाज़ार तक का रास्ता समझाइए, जैसे किसी अनजान को समझा रहे हों।"
**Shopping:** "सब्ज़ी मंडी में मोलभाव कैसे करते हैं? कल की खरीदारी बताइए — क्या लिया, कितने का।" *(prices exercise numbers naturally)*
**Banking & money:** "बैंक में खाता खोलने की प्रक्रिया समझाइए।" · "एक काल्पनिक रकम — जैसे ₹47,850 — किश्तों में कैसे बाँटेंगे, बोलकर समझाइए।"
**Medical:** "बुखार होने पर घर में क्या करते हैं? डॉक्टर को लक्षण कैसे बताएँगे?" *(never real medical history — invent the patient)*
**Travel:** "ट्रेन का टिकट कैसे बुक करते हैं? कोई यात्रा का अनुभव सुनाइए।"
**Education:** "अपने स्कूल के किसी प्रिय अध्यापक के बारे में बताइए।"
**Technology (naturally Hinglish):** "मोबाइल में recharge कैसे करते हैं? कोई app कैसे use करते हैं, step by step बताइए।"
**Government & services:** "आधार कार्ड बनवाने की प्रक्रिया क्या है? राशन कार्ड के लिए क्या करना पड़ता है?"
**Names:** "अपने पसंदीदा खिलाड़ियों/अभिनेताओं के नाम लेकर उनके बारे में बताइए।" *(public figures only)*
**Numbers & dates:** "एक काल्पनिक फ़ोन नंबर बोलिए और दोहराइए।" · "भारत के प्रमुख त्योहार किस महीने में आते हैं, तारीखों के साथ।" *(one session in Hindi numerals, one mixing English — both are wanted)*
**Addresses:** "एक **काल्पनिक** पता बोलिए — मकान नंबर, गली, इलाक़ा, शहर, पिन कोड।" *(NEVER a real home address)*
**Code-mixed Hinglish (its own sessions, 15–25% of the corpus):** "अपनी last online shopping के बारे में बताइए — delivery, return, refund, जो भी हुआ।" · "office के किसी meeting का किस्सा।"
**Emergency (described, never real):** "मान लीजिए रसोई में आग लग जाए — आप फ़ोन पर कैसे मदद माँगेंगे? बोलकर दिखाइए।"
**Formal/read sessions (limited, labelled):** reading a provided neutral passage; news-style delivery allowed **only** here.

**PII rule inside prompts:** phone numbers, addresses, account numbers, and patient details are always **invented**. Names of private individuals are avoided — use public figures or fictional names.

## 5. File Naming Convention

```
SPK<nn>_<category>_<env>_<take>.<ext>
e.g.  SPK07_shopping_clean_02.wav
      SPK03_hinglish_noisy_01.m4a
      SPK11_numbers_phone_01.wav
```
- **SPK ids** are assigned by the corpus coordinator at consent time, one per person, never reused, never containing the person's name.
- `<category>` from §4's list; `<env>` one of `clean|noisy|outdoor|phone`; `<take>` two digits, incremented per clip in that combination.
- **Final clip identity is the file's content hash, assigned at intake** — the filename is for humans and duplicates are caught by hash even if renamed. Never re-export or re-encode a file (that changes the hash and hides duplicates); upload the original.

## 6. Metadata Sheet

One row per clip, in the shared sheet, filled **at upload time, not from memory later**:

| Column | Example |
|---|---|
| Filename | `SPK07_shopping_clean_02.wav` |
| Speaker ID | SPK07 |
| Consent reference | CONS-SPK07 (signed form on file) |
| Gender | F |
| Age band | 31–45 |
| Region (grew up speaking) | East UP |
| Native Hindi? | yes / second-language |
| Recording device | Redmi Note 12, RecForge (WAV) |
| Environment | indoor-clean / indoor-noisy / outdoor / telephony |
| Perceived noise | low / medium / high |
| Style | spontaneous / read / formal |
| Code-mixed? | yes / no |
| Topic category | shopping |
| Duration (s) | 38 |
| Collector | (collector's id) |
| Date recorded | 2026-08-12 |
| Notes | "scooter passed at 0:20" |

A clip without a complete row is not reviewable and will sit unaccepted until the row exists.

## 7. Quality Control — accept/reject rules

Reviewers listen to every clip in full. **REJECT** (reason logged) for any of:

- **Wrong language:** predominantly English or another language (Hinglish is fine — that's a category, not a defect)
- **Synthetic or played-back speech:** TTS voices, assistant voices, any audio of an audio (phone playing another recording) — listen for speaker-through-speaker artifacts
- **Rights-encumbered background:** TV, radio, songs, or any recognizable media audible — even faintly
- **PII:** real phone numbers, real home addresses, account numbers, real medical details, full names of private persons in sensitive context
- **Clipping/distortion:** waveform slammed at maximum, crackling
- **Too quiet:** speech not clearly above the noise floor at normal playback volume
- **Read-when-spontaneous:** obvious reading rhythm in a session labelled spontaneous
- **Coaching audible:** collector's voice prompting mid-clip ("अब बोलिए…")
- **Duplicate content:** the same speaker saying essentially the same rehearsed passage again, or two speakers reciting an identical script (each prompt should get *that speaker's* answer, not a shared script)
- **Out of bounds:** <2 s or >120 s of content; >30% silence/non-speech; more than one primary speaker (unless the session was an explicit multi-speaker case)
- **Broken chain:** no metadata row, no consent on file, or a re-encoded/exported file instead of the original

Borderline audio (mild noise, one distant horn) is **accepted** — the noisy slices need real imperfection. Rejection is for defects, not for realism. Trimming >2 s of leading/trailing silence happens at intake and is not a rejection reason.

## 8. Collector Checklist — one page

**Before the session**
- ☐ Consent form signed and filed; SPK id assigned by the coordinator
- ☐ Session type agreed (spontaneous / read / formal; clean / noisy / outdoor / phone)
- ☐ Recorder set to WAV/FLAC or highest quality; test clip made and heard back
- ☐ TV, music, other media OFF; phone on Do Not Disturb

**Brief the speaker (say this)**
- ☐ "Speak naturally, like on a normal phone call. Mistakes, pauses, and English words are fine — do not restart."
- ☐ "All numbers, addresses, and personal details must be made up."

**During**
- ☐ Mic a hand-span away · ☐ You stay silent while they speak · ☐ One prompt per clip, 15 s–2 min · ☐ 8–12 clips, varied categories from the session plan

**After**
- ☐ Files named `SPK<nn>_<category>_<env>_<take>` — originals, never re-exported
- ☐ Metadata row completed for every clip, same day
- ☐ Upload originals to `corpus-inbox/` (never email/WhatsApp them)
- ☐ Tell the coordinator the session is up for review

## 9. Common Mistakes — the ones that destroy corpus quality

1. **Reading everything.** A corpus of read speech measures reading, not speaking. Spontaneous means spontaneous.
2. **Performing.** Slow, over-clear "recording voice" is not how anyone talks to the product.
3. **The same sentence forever.** Ten near-identical takes teach us nothing; ten different answers teach us ten things.
4. **One super-speaker.** Forty clips from one enthusiastic cousin unbalance the whole corpus — the cap is 15, the target is 8–12.
5. **Family members copying each other.** Everyone in the household answering the same prompt with the same rehearsed story is duplicate content in different voices.
6. **YouTube/TV/radio audio, or any existing recording.** Instant rejection, and dangerous to the corpus's legal cleanliness. We only record live humans who signed our form.
7. **Background media.** The TV "just quietly on" ruins otherwise good clips — it is both a rights problem and a rejection.
8. **Playback re-recording.** Recording a phone playing someone's voice memo is not that person speaking.
9. **Real personal data.** A real phone number spoken aloud lives in the corpus forever. Everything sensitive is invented.
10. **"Cleaning up" speech.** Asking the speaker to drop their "अं…" and restarts — the fillers are wanted. (The same applies later in transcription: nothing is tidied.)
11. **Messaging-app transfers.** WhatsApp recompresses audio invisibly. Move original files only.
12. **Metadata from memory, days later.** Wrong region/device/environment labels poison analysis silently. Fill the row at upload.
13. **Re-encoding or renaming into new exports.** Changes the content hash, defeats duplicate detection, and breaks the chain from consent to clip.
14. **Recording without consent filed first.** No signed form, no recording — there is no "we'll sort the paperwork later" in a permanent asset.

---

*Questions during collection go to the corpus coordinator. When in doubt: record naturally, invent all personal details, upload the original, log it the same day.*
