# Hindi Transcription & Annotation Convention v1

| | |
|---|---|
| **Status** | v1 — the permanent annotation law. Versioned with the corpus; a change to this document is a corpus version boundary. |
| **Companions** | [Corpus Specification v1](hindi-evaluation-corpus-spec.md) · [Collection Guide v1](hindi-corpus-collection-guide.md) — both frozen; this document completes the set. |
| **The test of this document** | Two expert transcribers, working independently on the same recording, produce the **same reference text**. Wherever they could differ, this document decides — nothing is left to taste. |

## 1. Purpose

This convention standardises how human transcribers create the reference text for every clip in the Hindi evaluation corpus. The reference is the ground truth every future measurement is scored against, forever.

**The reference represents what was spoken. Never what "should" have been spoken.** A reference that tidies, corrects, or interprets the speaker measures the transcriber's Hindi, not the speaker's — and poisons every number computed from it.

## 2. General Principles

1. **Verbatim.** Every spoken word appears; no unspoken word appears.
2. **No grammar correction.** Wrong gender agreement, dropped postpositions, broken sentences — transcribed exactly as spoken.
3. **No sentence rewriting, no reordering, no completion** of what the speaker "meant".
4. **No punctuation.** No danda, comma, question mark, quotes — nothing. Speech has no punctuation; adding it imports transcriber variance.
5. **No capitalisation as style.** Latin text is lowercase, with exactly one deterministic exception (§3.5, letter-name initialisms).
6. **No beautification, no spelling "fixes" of pronunciation.** If the speaker said गवरमेंट, write गवरमेंट, not सरकार and not government.
7. **No interpretation.** If you can only guess, you do not write your guess — see §8.
8. When two rules seem to conflict, the more specific section wins; genuinely undecided cases go to reconciliation and the resolution is appended to this convention's word lists (§10) — never improvised per clip.

## 3. Hindi Writing Rules

### 3.1 Base script
Hindi speech is written in **standard modern Devanagari**, dictionary spelling for real words, phonetic Devanagari for names and dialect words.

### 3.2 Nuqta — deterministic
- Use ज़ फ़ ड़ ढ़ **when the speaker pronounces the fricative/flap**: ज़रूरी, फ़ोन, सड़क, पढ़ाई. If the speaker says जरूरी (no fricative), write जरूरी.
- **Never** use क़ ख़ ग़ — always write क ख ग (the distinction is not reliably audible across speakers; folding it removes a permanent source of disagreement).

### 3.3 Anusvāra / candrabindu
Follow standard dictionary spelling per word: हिंदी, संडे-class words with anusvāra; हाँ, माँ, आँख, कहाँ, जहाँ with candrabindu. The reconciliation word list (§10) is the tiebreaker of record.

### 3.4 Loanwords — the Devanagari list
Everyday assimilated loanwords are written in **Devanagari**, per the frozen starter list (appendable only through reconciliation):
बस, स्कूल, कॉलेज, ट्रेन, स्टेशन, डॉक्टर, दवाई, फ़ोन, मोबाइल, कंप्यूटर, इंटरनेट, टिकट, पुलिस, बैंक, पैसा, ऑफिस, होटल, बाज़ार, गाड़ी, रोड, लाइन, टाइम, फोटो, सिम, पिन (spoken as words), रिचार्ज, नंबर, मीटर, लीटर, किलो, डिग्री, बोतल, ग्लास, टेबल, कुर्सी, पेन, कॉपी, बिल, चेक (bank), फॉर्म, कार्ड

### 3.5 Abbreviations and initialisms — deterministic by how they were spoken
- **Spoken letter-by-letter** (ए-टी-एम, ओ-टी-पी…) → **Latin capitals**: ATM, OTP, TV, ID, SMS, EMI, PIN (if spelled पी-आई-एन), GPS, CCTV, UPI.
- **Spoken as a word** (सिम, पिन, नासा…) → treated as a word: Devanagari if on the loanword list or Hindicised (सिम, पिन), Latin lowercase if spoken as English (laser).

### 3.6 Brand and product names
Always **Latin lowercase**, as one token stream matching common written form: whatsapp, paytm, google pay, amazon, aadhaar (brand-like usage), youtube, jio, irctc → IRCTC only if spelled letter-by-letter (§3.5 wins).

### 3.7 English words
English lexical items spoken with English phonology → **Latin lowercase** (§9 governs all mixing). Everything that is not English (including Urdu, Punjabi, Bhojpuri words inside Hindi speech, and all proper names of people/places spoken in the Hindi flow) → **Devanagari**, phonetically if unknown.

## 4. Numeral Rules — digits never appear in a reference

Every number is written **as words, exactly as spoken, in the language it was spoken in**. The digit characters 0–9 and ०–९ never appear in reference text, and neither do symbols (₹ % : /).

| Spoken | Reference |
|---|---|
| "पचपन" | पचपन |
| "फिफ्टी फाइव" (English phonology) | fifty five |
| "दो हज़ार चौबीस" (year) | दो हज़ार चौबीस |
| "नाइनटीन नाइंटी एट" | nineteen ninety eight |
| "साढ़े चार बजे" | साढ़े चार बजे |
| "टेन थर्टी ए एम" | ten thirty AM |
| "पैंतालीस परसेंट" | पैंतालीस percent |
| "पचास प्रतिशत" | पचास प्रतिशत |
| "तीन सौ रुपये" | तीन सौ रुपये |
| "टू थाउज़ेंड रुपीज़" | two thousand रुपये *(only if रुपये was said in Hindi; if "rupees", write rupees)* |
| Phone number "नौ आठ सात छह..." digit-by-digit | नौ आठ सात छह … *(each digit as the word spoken)* |
| "डबल नौ" | डबल नौ |
| OTP "फोर सेवन टू नाइन" | four seven two nine |
| PIN code "एक one one zero शून्य आठ" (mixed) | एक one one zero शून्य आठ *(each digit in its spoken language)* |
| "पंद्रह अगस्त उन्नीस सौ सैंतालीस" | पंद्रह अगस्त उन्नीस सौ सैंतालीस |
| Address "मकान नंबर बी बारह" | मकान नंबर B बारह *(letter-name B per §3.5)* |

The rule is mechanical: transcribe the **words the mouth produced**, digit by digit, unit by unit, in the script their language demands. There is no case where a transcriber "formats" a number.

## 5. Fillers — all kept, canonical spellings fixed

Fillers are speech and are **always transcribed**. To keep two transcribers identical, every filler has exactly one spelling:

| Sound | Write | Sound | Write |
|---|---|---|---|
| Hindi hesitation vowel | अं | nasal hum (any language) | हम्म |
| longer hesitation | आं | agreement backchannel | हाँ |
| मतलब (as filler or word) | मतलब | अच्छा (backchannel) | अच्छा |
| तो (dangling) | तो | यानी | यानी |
| ना (tag: "है ना") | ना | ठीक है | ठीक है |
| English hesitation | um / uh (as heard) | okay (any of ok/okay/oke) | okay |
| like (filler) | like | actually | actually |
| you know | you know | so (English filler) | so |

**Examples:** "अं मैं कल अं बाज़ार गया था" → `अं मैं कल अं बाज़ार गया था` · "तो basically हम्म हमने okay कर दिया" → `तो basically हम्म हमने okay कर दिया`. Removing a filler is falsifying the recording.

## 6. False Starts, Repeats, Corrections, Stuttering

- **Interrupted (incomplete) word:** transcribe the fragment as heard with a **trailing dash**: "जा-" for an abandoned जाना. Each incomplete attempt gets its own dash: `म- म- मुझे`.
- **Restarted word (completed on retry):** fragment with dash, then the full word: `स- स्टेशन`.
- **Repeated whole words:** written as many times as spoken, no dash: `मैं मैं वहाँ गया`.
- **Self-correction:** both the wrong and the corrected version, in spoken order, nothing marked: "सोमवार को नहीं मंगलवार को" → `सोमवार को नहीं मंगलवार को`.
- **Sentence restart:** everything spoken stays: `मुझे वो मैं कह रहा था कि वो ठीक है`.
- **Stuttering:** every audible attempt: `क- क- कल आना`.

The dash is the only annotation mark in the entire convention, and it means exactly one thing: *this word was not completed*.

## 7. Non-Speech Events — never in the reference

Laughter, coughs, sneezes, door slams, dog barking, vehicles, music, crowd noise, and silence **never appear in reference text** — a bracketed tag would survive scoring as a fake word. They are logged in the clip's structured notes using the fixed tag set: `laughter cough sneeze door dog vehicle music crowd tv-rejected other` (music/tv presence normally means the clip was already rejected at QC).

- Speaker laughs **between** words → nothing in the reference, `laughter` in notes.
- Speaker laughs **while** saying a word → transcribe the word normally.
- Long pauses and silences → nothing; the reference has no timing.
- **Background speech by other people → never transcribed** (§8 if it threatens the primary speaker's intelligibility).

## 8. Difficult Audio

- **Unclear span:** both transcribers attempt it independently, marking the span as uncertain in their worksheet (not in the reference). If reconciliation reaches certainty → the agreed text stands. If not → **the clip is rejected**; the evaluation corpus never contains a guessed reference. Rejections are logged with reasons.
- **Overlapping speakers:** the primary speaker is transcribed; the overlapping voice is not. If overlap makes the primary speaker uncertain → the span is uncertain → the rejection rule above applies.
- **Unknown words** (dialect terms, unfamiliar names): transcribed **phonetically in Devanagari**, flagged to reconciliation; the agreed phonetic form is final and is added to the word list if likely to recur.
- **Foreign non-English words** inside Hindi speech (Urdu, Punjabi, Marathi…): Devanagari, phonetically — only English earns Latin script (§9).
- **Rejection belongs to QC and reconciliation, not to individual transcribers:** a transcriber never skips a clip on their own; they transcribe what they can, mark uncertainty, and the process decides.

## 9. Hinglish Rules — the script decision procedure

Apply **in order**, per word; the first matching rule decides:

1. **Letter-name initialism** (spoken letter-by-letter) → Latin CAPITALS. (ATM, OTP, EMI)
2. **Brand/product name** → Latin lowercase. (whatsapp, paytm, jio)
3. **On the Devanagari loanword list** (§3.4, incl. reconciliation additions) → Devanagari. (स्कूल, फ़ोन, रिचार्ज)
4. **Word carries fused Hindi morphology** (Hindi plural/oblique/case ending welded onto the stem) → Devanagari: मीटिंगों, फ़िल्में, ट्रेनों, डॉक्टरों.
5. **English lexical item spoken with English phonology** → Latin lowercase: meeting, delivery, refund, cancel, actually, battery, screen.
6. **Everything else** (Hindi, names, other languages) → Devanagari.

**Worked patterns:**
- English noun + Hindi grammar around it: `meeting में late हो गया`
- English verb + Hindi light verb: `use करना` · `download हो गया` · `cancel कर दो`
- Fused morphology flips the script: `meeting में` but `मीटिंगों में` · `train से` but `ट्रेनों की`
- The same concept both ways in one clip is normal — follow the mouth each time: `फ़ोन उठाओ` … `phone is dead यार`
- An entire English sentence embedded stays Latin: `मैंने बोला I will call you back फिर कट गया`

## 10. Review Process

1. **Qualification:** a transcriber is fluent in Hindi, has studied this document, and passes a **calibration set** (10 pre-solved clips, ≥95% token agreement with the gold references) before touching corpus audio.
2. **Independent double transcription:** Transcriber A and Transcriber B work on the same audio **without contact** — no shared drafts, no discussion, different sittings.
3. **Comparison:** the two references are diffed token-by-token; the disagreement count per clip is recorded.
4. **Reconciliation:** A and B (with the corpus coordinator as tiebreaker) resolve each difference **by citing a rule in this document**. A difference no rule decides becomes a new word-list entry or a logged convention gap — appended, dated, never improvised.
5. **Logging:** every disagreement and its resolution goes to the reconciliation log (clip id, span, A's version, B's version, resolution, rule cited). The **corpus-level disagreement rate** is computed from step 3 and recorded in the corpus provenance — it is the honest floor of what any measurement on this corpus can claim.
6. **Acceptance:** a clip is accepted when a single agreed reference exists with zero unresolved spans. **Rejection:** any unresolved uncertainty (§8) rejects the clip; rejection is logged, never silent.

## 11. Examples

Reference text is shown between backticks; everything follows every rule above (no punctuation, no digits, lowercase Latin, dashes only for incomplete words).

**Conversation / daily life**
1. `कल सुबह मैं छह बजे उठा और सैर पर चला गया`
2. `हमारे मोहल्ले में एक छोटा सा पार्क है जहाँ बच्चे खेलते हैं`
3. `बारिश में तो हालत खराब हो जाती है भाई पानी भर जाता है`
4. `अं मैं सोच रहा था कि इस बार छुट्टी में घर जाऊँ`
5. `खाना बनाते बनाते गैस खत्म हो गई तो पड़ोस से सिलेंडर माँगा`

**Hinglish / code-mixed**
6. `मैंने कल online order किया था अभी तक delivery नहीं आई`
7. `boss ने बोला कि meeting reschedule हो गई है`
8. `यार battery खत्म हो रही है charger देना ज़रा`
9. `उसका attitude मुझे बिल्कुल पसंद नहीं actually`
10. `मैं थोड़ा busy हूँ आपको call back करता हूँ`
11. `traffic इतना था कि office पहुँचते पहुँचते ग्यारह बज गए`
12. `मैंने बोला I will call you back फिर कट गया`
13. `ये app बार बार hang हो रही है uninstall करके फिर से install करो`

**Numbers**
14. `मेरे पास तीन सौ पचास रुपये बचे हैं`
15. `total bill two thousand five hundred हुआ था`
16. `दुकानदार ने पचहत्तर percent discount बोला मुझे यकीन नहीं हुआ`
17. `नौ आठ सात छह पाँच चार तीन दो एक शून्य`
18. `डबल नौ पाँच सात सिक्स फोर`
19. `OTP आया है four seven two nine`
20. `पिन कोड एक one one zero शून्य आठ है`

**Dates, times, years**
21. `पंद्रह अगस्त उन्नीस सौ सैंतालीस को आज़ादी मिली थी`
22. `मेरी शादी दो हज़ार अठारह में हुई थी`
23. `train साढ़े पाँच बजे की है platform नंबर दो से`
24. `appointment twelve thirty PM का है`
25. `अगले month की पच्चीस तारीख को exam है`

**Names**
26. `मुझे सचिन तेंदुलकर की batting बहुत पसंद थी`
27. `हमारे यहाँ शर्मा जी की दुकान मशहूर है`
28. `मेरा दोस्त फ़िरोज़ लखनऊ में रहता है`
29. `अमिताभ बच्चन की पुरानी फ़िल्में ही अच्छी थीं`

**Addresses (always fictional)**
30. `मकान नंबर B बारह गली नंबर चार शास्त्री नगर नई दिल्ली`
31. `flat number two zero one green view apartment सेक्टर बाईस`
32. `पता है दुकान नंबर सात मेन रोड रामपुर पिन दो एक एक शून्य शून्य एक`

**Medical**
33. `दो दिन से बुखार है और बदन दर्द भी हो रहा है`
34. `डॉक्टर ने दिन में तीन बार दवाई लेने को बोला है`
35. `BP की problem है तो नमक कम खाता हूँ`
36. `x-ray कराया था report कल मिलेगी`

**Shopping**
37. `आलू कितने के किलो दिए भैया`
38. `थोड़ा कम कर लो पचास ज़्यादा बोल रहे हो`
39. `size medium का दिखाइए ये वाला बड़ा है`
40. `cash नहीं है whatsapp pe नहीं paytm से कर दूँ`

**Banking**
41. `खाता खोलने के लिए aadhaar card और photo चाहिए`
42. `EMI हर month की सात तारीख को कटती है`
43. `ATM से पैसे निकाले तो receipt नहीं आई`
44. `cheque clear होने में दो दिन लगते हैं`

**Technology**
45. `recharge करने के लिए पहले app खोलो फिर mobile number डालो`
46. `wifi का password क्या है भाई`
47. `video call में आवाज़ कट कट के आ रही है`

**Government / services**
48. `राशन कार्ड के लिए form भरकर दफ्तर में जमा करना पड़ता है`
49. `driving licence renew कराना है online हो जाता है क्या`
50. `बिजली का बिल इस बार ज़्यादा आया है complaint करनी पड़ेगी`

**Fillers, false starts, corrections, stutter**
51. `अं तो मैं ये कह रहा था कि हम्म प्लान ठीक है`
52. `म- म- मुझे वो वाली फ़िल्म देखनी है`
53. `स- स्टेशन पर मिलते हैं ठीक है ना`
54. `सोमवार को नहीं नहीं मंगलवार को आना`
55. `मैं मैं तो पहले ही बोल चुका था like पहले ही`
56. `उसने बोला कि जा- अं छोड़ो जाने दो`

**Grammar kept as spoken (never corrected)**
57. `मेरे को ये वाला अच्छा लगता है` *(not मुझे)*
58. `हम कल जाएगा गाँव` *(agreement error kept)*

**Phone-call style**
59. `हैलो हाँ भैया बोलिए अच्छा अच्छा ठीक है पहुँच जाऊँगा`
60. `आवाज़ नहीं आ रही आपकी हैलो हैलो अब बोलिए हाँ`

---

*Every future Hindi corpus version transcribes under this convention. Amendments happen only through the reconciliation process, are dated, and imply a corpus version boundary — a reference written under v1 is never re-read under v2.*
