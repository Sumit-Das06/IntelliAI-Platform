"""Normalization profiles — the ruler a text metric is computed with.

A metric's identity is *computation plus normalisation*. `wer_unicode`
says how two token sequences are compared; the profile says what a token
is. Two numbers computed with different profiles are not comparable, in
the same way that two numbers from different corpus versions are not:
the comparison would be decided by the ruler rather than by the models.

**A profile is an evidence object, not a language object** (founder
ruling, B2). It is identified by ``name@vN`` and nothing else — it
carries no language, no script, and no product meaning. The consequences
are deliberate:

- several languages may share one profile, and today several do;
- one language may move between profile versions over time, which is a
  change in how it is measured and therefore a comparability boundary;
- an evidence record cites the exact ``name@vN`` it used, so the ruler is
  read from the record rather than re-derived from the language years
  later, when the binding may well have moved.

**Why versioned, when metric names are not.** A metric name is permanent
and unrenameable, so a ruler that turns out wrong must be correctable
*without* minting a new metric name. Versioning the profile is what buys
that: `@v2` corrects the ruler, every historical number stays valid under
`@v1`, and the two are structurally incomparable rather than accidentally
averaged. Released versions are immutable — the same law as datasets and
migrations.

**The category trap this module is built around.** Arabic tashkeel and
Devanagari matras are both Unicode category ``Mn``. A profile that strips
category M to de-diacritise Arabic destroys Hindi. So folds are an
*enumerated codepoint table* and never a category rule, and the registry
refuses a fold key that names a Unicode general category.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Final

from intelliai_evaluation.wer import normalize_words

#: Unicode general-category names, major and full. A fold table may never
#: be keyed on one of these: the whole point of an enumerated table is
#: that "strip the diacritics" is a claim about specific codepoints, and a
#: category rule that is correct for one script silently destroys another.
#:
#: The cost is that these literal characters can never be folded. For
#: speech normalisation that is free — no profile here folds a Latin
#: letter — and if one ever needs to, the refusal is the conversation.
_CATEGORY_NAMES: Final[frozenset[str]] = frozenset(
    {"L", "M", "N", "P", "S", "Z", "C"}
    | {
        f"{major}{minor}"
        for major, minors in {
            "L": "ultmo",
            "M": "nce",
            "N": "dlo",
            "P": "cdseifo",
            "S": "mcko",
            "Z": "slp",
            "C": "cfson",
        }.items()
        for minor in minors
    }
)

_APOSTROPHE: Final = "'"


class ProfileNotRegisteredError(LookupError):
    """A ruler nothing defines. A record citing one cannot be reproduced."""


class DuplicateProfileError(ValueError):
    """A released ``name@vN`` may never be redefined — only superseded by @v(N+1)."""


class InvalidProfileError(ValueError):
    """The profile is not expressible as evidence (e.g. a category-named fold)."""


@dataclass(frozen=True)
class NormalizationProfile:
    """One ruler: text in, comparable tokens out.

    ``tokenize`` is the implementation; the declared fields above it are
    the identity a reader recovers from a record. For every profile built
    by :func:`unicode_profile` the two cannot drift, because the tokenizer
    is *derived from* the declared fields.
    """

    name: str
    version: int
    description: str
    tokenize: Callable[[str], list[str]]
    #: Enumerated codepoint -> replacement (``""`` deletes). Never a category.
    #: A read-only mapping: a released ruler that could be edited in place
    #: would silently change what every number computed under it means.
    codepoint_folds: Mapping[str, str] = field(default_factory=lambda: MappingProxyType({}))

    @property
    def id(self) -> str:
        """The citation form an evidence record carries."""
        return f"{self.name}@v{self.version}"

    def words(self, text: str) -> list[str]:
        """The word tokens WER is computed over."""
        return self.tokenize(text)

    def characters(self, text: str) -> list[str]:
        """The character sequence CER is computed over.

        Word tokens joined by a single space, then split into characters:
        the inter-word boundary counts as one character, so an erroneously
        merged or split word costs exactly one edit rather than being
        invisible. Derived from :meth:`words` on purpose — CER and WER
        must never disagree about what the text *was*.
        """
        return list(" ".join(self.tokenize(text)))


def unicode_profile(
    *,
    name: str,
    version: int,
    description: str,
    keep_categories: tuple[str, ...] = ("L", "M", "N"),
    remove_categories: tuple[str, ...] = (),
    codepoint_folds: Mapping[str, str] | None = None,
) -> NormalizationProfile:
    """Build a profile whose tokenizer *is* its declared fields.

    ``keep_categories`` survive as word content; ``remove_categories`` are
    deleted outright; everything else becomes a space, which is what
    separates words. The distinction between "removed" and "spaced" is not
    cosmetic — spacing a zero-width joiner splits one word into two.
    """
    folds = dict(codepoint_folds or {})
    kept = tuple(keep_categories)
    removed = frozenset(remove_categories)

    def tokenize(text: str) -> list[str]:
        composed = unicodedata.normalize("NFC", text.casefold())
        pieces: list[str] = []
        for char in composed:
            folded = folds.get(char, char)
            for ch in folded:
                category = unicodedata.category(ch)
                if category in removed or category[0] in removed:
                    continue
                if category in kept or category[0] in kept or ch == _APOSTROPHE:
                    pieces.append(ch)
                else:
                    pieces.append(" ")
        return [
            stripped for word in "".join(pieces).split() if (stripped := word.strip(_APOSTROPHE))
        ]

    return NormalizationProfile(
        name=name,
        version=version,
        description=description,
        tokenize=tokenize,
        codepoint_folds=MappingProxyType(folds),
    )


class NormalizationRegistry:
    """The namespace of rulers, keyed by ``name@vN``.

    Registration refuses a released identity rather than replacing it: a
    profile version is quoted by evidence that outlives this process, so
    redefining ``devanagari@v1`` would silently change what a five-year-old
    number means. Corrections are always the next version.
    """

    def __init__(self) -> None:
        self._profiles: dict[str, NormalizationProfile] = {}

    def register(self, profile: NormalizationProfile) -> NormalizationProfile:
        if profile.id in self._profiles:
            raise DuplicateProfileError(
                f"profile {profile.id} is already registered; released versions are "
                "immutable because evidence cites them. Correct a ruler with "
                f"{profile.name}@v{profile.version + 1}, never by redefining this one."
            )
        for key in profile.codepoint_folds:
            # The category check runs FIRST even though the length check
            # would also catch a two-letter name: someone writing {"Mn": ""}
            # is trying to strip diacritics wholesale, and "that is not a
            # codepoint" does not tell them why they must not.
            if key in _CATEGORY_NAMES:
                raise InvalidProfileError(
                    f"profile {profile.id}: fold key {key!r} names a Unicode general "
                    "category. Category folds are refused: Arabic tashkeel and "
                    "Devanagari matras are both Mn, so a category rule that "
                    "de-diacritises one script destroys the other. Enumerate the "
                    "codepoints you mean."
                )
            if len(key) != 1:
                raise InvalidProfileError(
                    f"profile {profile.id}: fold key {key!r} is not a single codepoint. "
                    "Folds are an enumerated table; a rule is not expressible here."
                )
        self._profiles[profile.id] = profile
        return profile

    def require(self, identity: str) -> NormalizationProfile:
        """The profile a record cites, or a refusal naming what is known."""
        profile = self._profiles.get(identity)
        if profile is None:
            known = ", ".join(sorted(self._profiles)) or "none"
            raise ProfileNotRegisteredError(
                f"unknown normalization profile {identity!r}; registered: {known}"
            )
        return profile

    def get(self, identity: str) -> NormalizationProfile | None:
        return self._profiles.get(identity)

    def __contains__(self, identity: object) -> bool:
        return identity in self._profiles

    def __iter__(self) -> Iterator[NormalizationProfile]:
        return iter(self._profiles.values())

    def __len__(self) -> int:
        return len(self._profiles)

    def identities(self) -> tuple[str, ...]:
        return tuple(sorted(self._profiles))


# ── The registered rulers ────────────────────────────────────────────

#: The frozen English ruler, wrapping `wer.normalize_words` unchanged.
#:
#: It is a legacy anchor, and that is its entire job: it is the ruler
#: behind every committed English baseline, including records written
#: before profiles existed and which therefore cite no profile at all.
#: Its behaviour may never change — a correction would be a different
#: profile, and re-measuring the 2026-08-03 baseline under it must give
#: the same number forever.
ASCII_EN_V1: Final = NormalizationProfile(
    name="ascii_en",
    version=1,
    description=(
        "Lowercase; everything outside [a-z0-9 '] becomes a space; edge "
        "apostrophes stripped. Frozen since M2 step 0. Non-Latin text "
        "normalises to nothing under this ruler, which is why it must "
        "never be used for a language it was not built for."
    ),
    tokenize=normalize_words,
)

#: The generic Unicode ruler as first shipped, defect included.
#:
#: This pins `roundtrip.speech_normalize` exactly: casefold, NFC, keep
#: categories L/M/N plus apostrophes, everything else to a space. That
#: last clause is a known defect — ZWJ and ZWNJ are category Cf, so they
#: become spaces and SPLIT a word in two, inflating both reference and
#: hypothesis counts.
#:
#: It is registered with the defect on purpose. It is the ruler behind the
#: committed kokoro-82m round_trip_wer numbers, and a profile version is
#: immutable once evidence cites it. The correction is @v2.
UNICODE_GENERIC_V1: Final = unicode_profile(
    name="unicode_generic",
    version=1,
    description=(
        "casefold, NFC, keep Unicode categories L/M/N and apostrophes; all "
        "else becomes a space. Format characters (Cf) therefore split words. "
        "Frozen: this is the ruler the committed synthesis baselines used."
    ),
)

#: The corrected generic Unicode ruler: format characters are REMOVED.
#:
#: ZWJ/ZWNJ control conjunct formation in Devanagari and joining in
#: Arabic; they are not word boundaries in any script. Deleting rather
#: than spacing them is the single change from @v1, and it is correct for
#: every script rather than for one — which is why this is a version of
#: the generic ruler and not a language-named profile. A profile is an
#: evidence object; the languages that bind to it are policy.
#:
#: Devanagari needs nothing further: NFC already converges the two nukta
#: spellings (U+0958 and U+0915 U+093C), matras are Mn and survive as word
#: content, and danda is Po and already separates words.
UNICODE_GENERIC_V2: Final = unicode_profile(
    name="unicode_generic",
    version=2,
    description=(
        "casefold, NFC, remove format characters (Cf), keep Unicode "
        "categories L/M/N and apostrophes; all else becomes a space. "
        "Corrects @v1, whose Cf-to-space rule split conjuncts."
    ),
    remove_categories=("Cf",),
)


def _build_registry() -> NormalizationRegistry:
    registry = NormalizationRegistry()
    for profile in (ASCII_EN_V1, UNICODE_GENERIC_V1, UNICODE_GENERIC_V2):
        registry.register(profile)
    return registry


PROFILES: Final = _build_registry()

#: Which ruler a language is measured with **today**. This is policy, not
#: identity: it may change, and when it does, past evidence stays valid
#: because every record cites the profile it actually used rather than the
#: language it was about. Never read this to interpret an old record —
#: read the record.
#:
#: `ar` is deliberately absent. Arabic needs an enumerated fold table
#: (tashkeel, alef variants, tatweel), those are linguistic decisions with
#: permanent evidential consequences, and there is no Arabic corpus and no
#: verifier yet. Inventing the policy before the evidence exists is how a
#: wrong ruler becomes permanent.
LANGUAGE_PROFILES: Final[Mapping[str, NormalizationProfile]] = {
    "en": UNICODE_GENERIC_V2,
    "hi": UNICODE_GENERIC_V2,
}


def profile_for(language: str) -> NormalizationProfile:
    """The ruler this language is measured with today.

    Refuses rather than defaulting. A language with no ruling has no
    ruler, and measuring it under a borrowed one is exactly how a
    Devanagari reference gets scored by an ASCII ruler and recorded, in an
    append-only ledger, as evidence about a model.
    """
    profile = LANGUAGE_PROFILES.get(language)
    if profile is None:
        known = ", ".join(sorted(LANGUAGE_PROFILES)) or "none"
        raise ProfileNotRegisteredError(
            f"no normalization profile is bound to language {language!r}; bound: {known}. "
            "Measuring it under another language's ruler would produce a plausible "
            "number about nothing."
        )
    return profile
