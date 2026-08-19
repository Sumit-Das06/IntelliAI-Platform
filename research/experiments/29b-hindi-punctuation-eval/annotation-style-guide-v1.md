# Hindi Punctuation Annotation Style Guide — v1 (M29B)

| | |
|---|---|
| **Version** | 1 (2026-08-19) |
| **Applies to** | the spontaneous Hindi slice of `hi-punct-eval@v2` |
| **Law** | this guide is PART OF THE BENCHMARK'S PROVENANCE — there is no universally "correct" punctuation style; scores against these references measure agreement WITH THIS GUIDE |

## Annotator record (honest, up front)

- **Annotator**: single annotator — the automated research assistant
  preparing this milestone (an AI system, **not a human native
  speaker**). This does not satisfy the "human annotator" ideal; it is
  the practical single-annotator option, and per the milestone rule the
  limitation is documented rather than hidden.
- **Review status**: PROVISIONAL — **native-speaker (founder) review is
  PENDING**; these references must be ratified or amended before any
  production gate depends on them.
- **Mode**: TEXT-ONLY. The annotator did NOT listen to audio. Every
  intonation-dependent decision (question vs statement, exclamation) is
  resolved from lexical cues alone — a real limitation for Hindi, where
  declarative-form questions are carried by intonation.
- **Exposure note**: the annotator had previously seen the lead model's
  outputs on E3 HYPOTHESES of some of these clips (M29A e3-sanity).
  Annotations were made from the reference texts top-to-bottom without
  consulting any model output, but the prior exposure is disclosed as a
  potential anchoring bias.
- **Word law**: annotation may ONLY insert marks from {।, ",", ?, !}.
  No word, spelling, or spacing change of any kind; the v2 builder
  REFUSES any annotation whose depunct differs from the source text.

## Rules

1. **Sentence enders**: Devanagari-matrix sentences end with "।" —
   never "." (the Latin full stop is reserved for English-matrix
   sentences, which this slice does not contain).
2. **Questions ("?")**: only when the text carries lexical question
   evidence — interrogative words with question intent (क्या, कौन, कब,
   कहाँ, क्यों, कैसे, कितना…), tag questions (…है ना, …है न, ठीक है
   ना), and greeting inquiries (क्या हालचाल है). Declarative-form
   questions WITHOUT lexical cues cannot be recovered from text and are
   annotated as statements — a documented, deliberate bias of v1.
3. **Exclamation ("!")**: only for lexically explicit exclamations
   (अरे वाह, क्या बात है). Emphasis audible only in audio is NOT
   annotated. (In practice: rare to absent in this slice.)
4. **Commas (",")** — sparing, "when in doubt, leave it out":
   - enumerations without conjunctions (नार्वे, स्वीडन, डेनमार्क…);
     no comma before a closing "और X";
   - after utterance-initial discourse fillers/vocatives when a full
     clause follows (जी सर, … / हाँ, … / देखिए, … / नमस्कार, …);
   - between coordinated clauses where a pause is grammatically
     standard (before लेकिन; between parallel clauses);
   - appositive/parenthetical asides (…रोहू, जो फिस बनाते हैं हमारे
     वर्कर्स, उसका…).
5. **Repetitions/fillers**: no marks INSIDE a repetition group
   (हाँ हाँ / नहीं नहीं नहीं stays unmarked internally). A filler group
   leading into a clause takes one comma after the group.
6. **Numbers**: never insert marks inside spoken digit or amount
   sequences (दो सौ बीस रूपये; नौ आठ सात…).
7. **English words inside Hindi**: no special treatment; the matrix
   language decides the sentence ender.
8. **Abbreviations/honorifics**: no "." after spoken honorifics (डॉ,
   श्री); ASR text carries no dotted abbreviations.
9. **URLs/emails**: never insert marks inside them (none occur in this
   slice).
10. **Fragments and truncated utterances**: every utterance-final
    position receives an ender (। or ?) even when the clip cuts
    mid-thought — the dictation-product convention. Truncation is
    flagged in `uncertain` instead of being left unpunctuated.
11. **`<unintelligible>` tokens**: kept verbatim, treated as an
    ordinary word for mark placement.
12. **Uncertainty**: any row where a defensible alternative punctuation
    exists (ambiguous question intent, truncated speech, filler-comma
    judgment) carries `"uncertain": true` with a one-line reason. These
    rows stay in the benchmark; the flag lets analysis split
    high-confidence rows from ambiguous ones.

## Known limitations of v1 (all deliberate, all documented)

- single annotator, AI, non-native, text-only, no inter-annotator
  agreement number;
- question recall is bounded by lexical cues (intonation questions are
  systematically annotated as statements);
- comma style is one defensible convention among several — comma F1
  against this guide measures style agreement more than correctness.
