"""Smart Transcript Correction (Milestone 57) — the M56-selected model
as a flag-gated, POST-FINAL product stage. STAGING ONLY; every
production overlay pins the flag off.

The two contracts, side by side (the M56 law):

* **Punctuation** (M30/M50): words MUST NOT change — a word-copy
  invariant the stage enforces mechanically.
* **Smart Correction** (this module): words MAY change, meaning MUST
  NOT — enforced by the language-scoped prompt contract plus the
  OUTPUT VALIDATION below; when validation fails the caller keeps the
  punctuated transcript (fail-open, like every stage before it).

Serving shape: an operator-managed pinned llama-server on its OWN port
(`tools/correction/launch_correction_gpu.py` refuses artifact drift),
so correction can never sit in the realtime llama-server's queue. The
runtime is loopback/compose-internal; the GATEWAY is the auth boundary
(same posture as /v1/transcribe and /v1/realtime).

M56 measured laws encoded here:

* language-scoped prompts (a combined prompt caused EN→HI translation
  flips; scoping removed them entirely);
* bounded generation (duration-scaled token budget; runaway output is
  a validation failure, never a served transcript);
* ambiguity bias: the prompt prefers preserving uncertain wording.
"""

# ruff: noqa: E501 — the prompt contracts are verbatim artifacts; wrapping them
# would change the shipped prompt.
from __future__ import annotations

import json
import re
import threading
import time
import unicodedata
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Final

import structlog

from intelliai_runtime_contract import RuntimeErrorType
from intelliai_runtime_core import RuntimeServiceError
from intelliai_stt_runtime.realtime import diagnose_repetition

logger = structlog.get_logger(__name__)

_ENGLISH: Final = frozenset({"en", "en-us", "en-in"})
_HINDI: Final = frozenset({"hi", "hi-in"})
_DEVANAGARI: Final = re.compile(r"[ऀ-ॿ]")
_DIGIT_RUN: Final = re.compile(r"\d{2,}")
_DECIMAL: Final = re.compile(r"\d+\.\d+")
_DEVANAGARI_DIGIT: Final = re.compile("[०-९]")  # noqa: RUF001 — Devanagari digit range, deliberate
_EMAIL_OR_URL: Final = re.compile(
    r"\b[\w.+-]+@[\w-]+\.[\w.]+\b|\bhttps?://\S+|\b[\w-]+\.(?:com|org|net|io|in)\b"
)

#: Input ceiling: beyond this the caller should use the async/pending
#: path rather than a blocking request (M56: latency grows with length).
MAX_INPUT_WORDS: Final = 600
#: Output may reformat but never balloon: a corrected transcript that is
#: >2.5x the input words is runaway or invention, not correction.
MAX_OUTPUT_RATIO: Final = 2.5

PROMPT_EN: Final = """You are a transcript-correction engine for ENGLISH speech-to-text output. Rewrite the user's transcript into clean, natural, grammatically correct English.

STRICT RULES:
1. NEVER change the meaning. Fix only language, never content. The output must be ENGLISH in Latin script — never translate or transliterate, no matter what names or words appear.
2. PRESERVE exactly: names of people/companies/products, numbers, amounts, currencies, dates, times, phone numbers, emails, URLs, IDs, and technical terms. Never turn a name into a different name or a number into a different number.
3. Do NOT add any information that is not in the input. Do NOT drop any information.
4. Remove speech artifacts: stutters/duplicated words ("i i want"), fillers ("um", "uh"), false starts — but keep intentional repetition ("very, very important").
5. Fix grammar, tense, articles, prepositions, capitalization, and punctuation. Split run-on speech into proper sentences. Do NOT replace the speaker's words with synonyms; keep their word choices.
6. Spoken formats become written formats: "support at intelliai dot com" -> "support@intelliai.com", spelled-out phone numbers/OTPs/codes/versions -> digits, currency amounts with a currency word -> symbol+digits.
7. Other numbers stay as the speaker said them (words stay words).
8. If a word is unclear or ambiguous and context does not clearly resolve it, KEEP the original wording. NEVER swap who did what to whom: keep the speaker's perspective and the direction of every action ("the file i sended you" means the speaker SENT it — it stays "the file I sent you", never "the file I received from you").
9. If the input is already correct, return it EXACTLY unchanged.
10. Output ONLY the corrected transcript text. No explanations, no quotes, no labels."""

PROMPT_HI: Final = """You are a transcript-correction engine for HINDI speech-to-text output. Rewrite the user's transcript into clean, natural, grammatically correct Hindi in DEVANAGARI script.

STRICT RULES:
1. NEVER change the meaning. Fix only language, never content. NEVER translate to English.
2. The output must be Hindi in Devanagari with proper danda (।) and question-mark punctuation. Hindi written in English letters ("mujhe kal office jana tha") IS Hindi: convert it to Devanagari — never answer in Latin script and never translate it to English. Mixed Hindi-English speech stays natural mixed Hindi in Devanagari (common loanwords like office/meeting/report/email as their usual Devanagari transliterations). EXCEPTION — technical terms, product names, brand names and acronyms (API, FastAPI, Python, Redis, PostgreSQL, CUDA, GPU, RAG, STT, TTS, version numbers, app names) stay in LATIN letters exactly as written; never transliterate or spell them out.
3. If the input is already correct Devanagari, return it EXACTLY unchanged — same words, same forms. When in doubt whether something needs fixing, DO NOT touch it. Change as FEW words as possible; never restyle (उसने stays उसने, never उन्होंने; ठीक तीन बजे keeps ठीक).
4. PRESERVE exactly: names of people/companies/products, numbers, amounts, dates, times, phone numbers, emails, URLs, and technical terms. Never turn a name into a different name or a number into a different number.
5. Do NOT add any information that is not in the input. Do NOT drop any information or qualifier words.
6. Remove speech artifacts: stutters/duplicated words, fillers — but keep intentional repetition ("हाँ हाँ", "जल्दी जल्दी"). Fix real grammar errors (gender/number agreement, tense), word forms, and punctuation. Split run-on speech into proper sentences. Do NOT replace the speaker's words with synonyms; keep loanwords as spoken (बर्थडे stays बर्थडे, not जन्मदिन).
7. Spoken formats become written formats ONLY for phone numbers, OTPs, codes, vehicle numbers, and currency amounts with a currency word; emails/URLs spoken as words become their written form. ALL other numbers stay exactly as the speaker said them, in words.
8. If a word is unclear or ambiguous and context does not clearly resolve it, KEEP the original wording. Read Roman-Hindi words by CONTEXT, not sound-alikes: "der" about time is देर (late), never डर (fear); "mat" as prohibition is मत. English words inside Roman Hindi (busy, free, late, call) are ENGLISH loanwords — keep them as their standard loanword form (बिज़ी, फ्री, लेट, कॉल, बर्थडे, गिफ्ट), never re-read them as Hindi words (busy is NEVER बसी) and never translate them (birthday stays बर्थडे, not जन्मदिन).
9. If the input is already correct Devanagari, return it EXACTLY unchanged.
10. Output ONLY the corrected transcript text. No explanations, no quotes, no labels."""


@dataclass(frozen=True)
class CorrectionResult:
    corrected_text: str
    model_ms: float
    validation: str  # "passed" — failures raise instead


class SmartCorrectionService:
    """HTTP client to the pinned correction llama-server + the output
    validation gate. No foundation-model library is imported here."""

    def __init__(
        self, url: str, *, timeout_seconds: float = 60.0, max_concurrency: int = 1
    ) -> None:
        self._url = url.rstrip("/")
        self._timeout = timeout_seconds
        self._probe_at = -1e9
        self._probe_verdict = "ready"
        # M58 concurrency cap: correction is a background convenience and
        # REALTIME STT OUTRANKS IT — excess jobs are refused loudly
        # (OVERLOADED -> a friendly retry upstream), never queued into an
        # invisible backlog that would hold the GPU hostage.
        self._slots = threading.Semaphore(max(1, max_concurrency))

    # -- health --------------------------------------------------------

    def probe(self) -> None:
        """Startup reachability: an ENABLED deployment with a dead
        backend refuses to serve (the fail-loud law)."""
        with urllib.request.urlopen(  # noqa: S310 — operator-configured internal URL
            f"{self._url}/health", timeout=5
        ) as response:
            if response.status != 200:
                msg = f"smart-correction backend unhealthy: {response.status}"
                raise RuntimeServiceError(RuntimeErrorType.NOT_READY, msg)

    def health(self) -> str:
        """``ready`` | ``degraded`` — cached probe, readiness stays cheap."""
        now = time.monotonic()
        if now - self._probe_at < 15.0:
            return self._probe_verdict
        self._probe_at = now
        try:
            self.probe()
            self._probe_verdict = "ready"
        except Exception:
            logger.warning("smart_correction_backend_degraded")
            self._probe_verdict = "degraded"
        return self._probe_verdict

    # -- correction ----------------------------------------------------

    def correct(self, text: str, language: str) -> CorrectionResult:
        tag = language.strip().casefold()
        if tag in _ENGLISH:
            prompt = PROMPT_EN
        elif tag in _HINDI:
            prompt = PROMPT_HI
        else:
            raise RuntimeServiceError(
                RuntimeErrorType.INVALID_INPUT, "unsupported correction language"
            )
        stripped = text.strip()
        if not stripped:
            raise RuntimeServiceError(RuntimeErrorType.INVALID_INPUT, "empty transcript")
        input_words = stripped.split()
        if len(input_words) > MAX_INPUT_WORDS:
            raise RuntimeServiceError(
                RuntimeErrorType.INVALID_INPUT,
                "transcript too long for correction; try a shorter selection",
            )

        payload = {
            "messages": [
                {"role": "system", "content": prompt + "\n/no_think"},
                {"role": "user", "content": stripped},
            ],
            "temperature": 0.0,
            "max_tokens": max(96, min(2048, len(input_words) * 4 + 64)),
        }
        request = urllib.request.Request(  # noqa: S310 — operator-configured internal URL
            f"{self._url}/v1/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        if not self._slots.acquire(blocking=False):
            logger.info("smart_correction_overloaded")
            raise RuntimeServiceError(
                RuntimeErrorType.OVERLOADED,
                "a correction is already running; try again in a moment",
            )
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:  # noqa: S310
                body = json.loads(response.read())
            output = str(body["choices"][0]["message"]["content"]).strip()
        except (OSError, urllib.error.URLError, KeyError, IndexError, ValueError) as exc:
            # No engine or backend names in the message (the M16 law).
            raise RuntimeServiceError(
                RuntimeErrorType.INTERNAL, "the correction backend did not answer in time"
            ) from exc
        finally:
            self._slots.release()
        model_ms = (time.perf_counter() - started) * 1000.0
        if "</think>" in output:
            output = output.rsplit("</think>", 1)[1].strip()
        self._validate(stripped, output, tag)
        return CorrectionResult(
            corrected_text=output, model_ms=round(model_ms, 1), validation="passed"
        )

    # -- output validation (the trust gate) ----------------------------

    def _validate(self, source: str, output: str, tag: str) -> None:
        def fail(reason: str) -> None:
            logger.warning("smart_correction_validation_failed", reason=reason)
            raise RuntimeServiceError(
                RuntimeErrorType.INTERNAL, "the correction result did not pass safety checks"
            )

        if not output.strip():
            fail("empty_output")
        out_words = output.split()
        source_words = len(source.split())
        if len(out_words) > max(8.0, source_words * MAX_OUTPUT_RATIO):
            fail("length_expansion")
        # M58: the mirror guard — catastrophic content COLLAPSE (the model
        # summarizing or deduplicating a long transcript down to a stub)
        # is dropped information, never served. The floor is deliberately
        # low (30%) so legitimate filler/stutter removal always passes;
        # short utterances are exempt ("हाँ हाँ हाँ" -> "हाँ" is fine).
        if source_words >= 20 and len(out_words) < source_words * 0.3:
            fail("content_collapsed")
        # Language contract: EN stays Latin; HI comes back in Devanagari.
        has_devanagari = bool(_DEVANAGARI.search(output))
        if tag in _ENGLISH and has_devanagari:
            fail("language_flip")
        if tag in _HINDI and not has_devanagari:
            fail("language_flip")
        # Protected content already in written form must survive:
        # digit runs, emails, and URLs from the input appear verbatim.
        squashed = unicodedata.normalize("NFC", output)
        for run in _DIGIT_RUN.findall(source):
            if run not in re.sub(r"[,\s]", "", squashed) and run not in squashed:
                fail("digits_changed")
        for decimal in _DECIMAL.findall(source):
            if decimal not in squashed:
                fail("decimal_changed")
        for token in _EMAIL_OR_URL.findall(source):
            if token.casefold() not in squashed.casefold():
                fail("entity_dropped")
        # The M56 entity-violation class: converting spoken/ASCII numbers
        # into Devanagari numerals (एक -> १) is a formatting mutation the
        # contract forbids — reject rather than serve.
        if _DEVANAGARI_DIGIT.search(output) and not _DEVANAGARI_DIGIT.search(source):
            fail("devanagari_digits_introduced")
        # Runaway repetition is never served (reuses the realtime guard).
        span_seconds = max(len(source.split()) / 3.0, 1.0)  # spoken-rate proxy
        if diagnose_repetition(output, span_seconds).pathological:
            fail("runaway_repetition")
        if "STRICT RULES" in output or "transcript-correction engine" in output:
            fail("prompt_leakage")


def build_smart_correction(settings: object) -> SmartCorrectionService:
    """Lifespan builder: flag ON + URL set, probed fail-loud."""
    url = str(getattr(settings, "smart_correction_url", "")).strip()
    if not url:
        msg = "smart correction enabled but INTELLIAI_STT_SMART_CORRECTION_URL is empty"
        raise RuntimeServiceError(RuntimeErrorType.NOT_READY, msg)
    service = SmartCorrectionService(
        url,
        timeout_seconds=float(getattr(settings, "smart_correction_timeout_seconds", 60.0)),
        max_concurrency=int(getattr(settings, "smart_correction_max_concurrency", 1)),
    )
    service.probe()
    return service
