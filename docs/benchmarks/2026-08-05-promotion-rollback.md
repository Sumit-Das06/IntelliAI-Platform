# A promotion and its rollback, executed — M5 step 5

**What this records.** One route replacement run end to end on real
artifacts, real runtimes, real evaluation records and real verdicts — and
then reverted. The procedure it exercises is
[PROMOTION.md](../../ml/evaluation/PROMOTION.md).

- **Date:** 2026-08-05 · **Host:** Intel Core i7-14650HX, Windows 11,
  native · **Slice:** `intelliai-stt` / `en` / `stt-eval-seed@v2`
- **Incumbent:** `reference` (the deterministic engine) ·
  **Candidate:** `whisper-small` v1, `cpu-int8`
- Both measured through live runtimes, each hosting only its own
  artifact, with the runner refusing to record a run against a runtime
  that is not hosting what the registry resolved.

## 1. Measure

| | Slice | WER | Hallucinated words |
|---|---|---|---|
| Incumbent | `intelliai-stt/en/reference@1/deterministic/stt-eval-seed@v2` | 1.000 | 7 |
| Candidate | `intelliai-stt/en/whisper-small@1/cpu-int8/stt-eval-seed@v2` | **0.000** | **0** |

## 2. Route replacement — the relative bar

```json
{ "verdict": "passed", "comparable": true, "findings": [],
  "wer_delta": -1.0, "hallucination_delta": -7, "regressed_clips": [] }
```

`comparable: true` is reported separately from the outcome on purpose:
*"the candidate lost"* and *"we cannot tell"* are different answers, and
collapsing them is how bad promotions happen.

## 3. Language enablement — the absolute bar

With the founder bar set to WER ≤ 0.15 for this demonstration (F-M5-3 is
still open, and the test **refuses** when no bar has been set):

```json
{ "verdict": "passed", "findings": [],
  "slice_slug": "intelliai-stt/en/whisper-small@1/cpu-int8/stt-eval-seed@v2" }
```

## 4. The diff *is* the promotion record

```diff
--- registry/catalog.py (before)
+++ registry/catalog.py (after)
     public_model_id="intelliai-stt",
     selector=RouteSelector(language="en"),
     status=LanguageStatus.SUPPORTED,
-    artifact_id="reference",
+    artifact_id="whisper-small",
     license=_WHISPER_SERVING_PATH,
     evidence=_STT_EN_EVIDENCE,
```

One line moves. Everything else — the promise, the ladder rung, the
serving-path licence, the evidence citations — is unchanged, which is the
whole point: a replacement changes *what serves*, not *what is promised*.

## 5. Rollback

```diff
-    artifact_id="whisper-small",
+    artifact_id="reference",
```

The revert needs **no new evidence and no new bar**. Run the switching
test in that direction anyway, and it says:

```json
{ "verdict": "refused", "comparable": true, "wer_delta": 1.0,
  "hallucination_delta": 7,
  "regressed_clips": ["en-tone-440hz-5s", "jfk-flac", "jfk-wav"],
  "findings": [ "hallucination_regression", "wer_regression", "clip_regressions" ] }
```

That verdict is correct and irrelevant. **A rollback is not a promotion.**
It restores a state that was already justified: the predecessor artifact
still exists (immutable and retained), its baseline still stands, and the
evidence that justified it never expired. Cheap rollback is the payoff of
routing-as-registry-state.

It is also this demonstration's **negative control**. A promotion
machinery that only ever says yes proves nothing; the same machinery,
given a genuine regression, refuses with three specific findings and
names the three clips that got worse.

## 6. What this demonstration did not do

- **It did not promote anything in the shipped catalog.** The catalogs
  above are constructed for the demonstration. Promoting a real route is
  a founder act requiring real evidence and an approval, and the shipped
  English route already has both.
- **It did not set a quality bar.** The 0.15 above is a demonstration
  value. F-M5-3 remains open, and until it is ruled, `enablement_test`
  refuses every language enablement with `no_absolute_bar` — which is the
  intended behaviour, not a gap.
- **It did not exercise voice rebinding.** That class needs listening
  evidence (F-M5-4) and a second voice-capable artifact; the switching
  half of its bar is the same function proven here.
