"""The source registry: one dated, license-verdict record per public source.

A source that cannot be used is still registered — BLOCKED is a status
with a reason, never an omission. License verdicts are facts read at a
source URL on a date; they decay and must be re-verified before any new
load-bearing use (RESEARCH_FRAMEWORK §2).
"""

from __future__ import annotations

import enum
from typing import Final

from pydantic import BaseModel, ConfigDict


class Access(enum.StrEnum):
    """Can this machine fetch the source right now?"""

    OPEN = "open"  # anonymous download works
    GATED = "gated"  # requires an authenticated, terms-accepted account
    BLOCKED = "blocked"  # unusable until a named condition is resolved


class CommercialVerdict(enum.StrEnum):
    YES = "yes"
    CONDITIONAL = "conditional"  # named condition (counsel/confirmation)
    NO = "no"


class SourceRecord(BaseModel):
    """Provenance of one public source, recorded before any byte is used."""

    model_config = ConfigDict(frozen=True)

    name: str
    reference: str  # canonical URL or HF id
    language: str  # primary language this record covers
    license: str  # verbatim license name as read at the source
    license_verified_on: str  # ISO date the license was read at source
    license_source_url: str
    commercial: CommercialVerdict
    access: Access
    access_detail: str = ""  # why gated/blocked, and what unblocks it
    speaker_ids: bool = False
    official_splits: bool = False
    contamination_risk: str = "undeterminable"  # none_known|possible|known_overlap|undeterminable
    notes: str = ""


# The registry for Milestone 15B. Every verdict below was read at source
# on the date shown, in the 2026-08-10/11 research sweeps or during 15B
# itself; the reports under docs/research/ carry the full evidence.
SOURCES: Final[tuple[SourceRecord, ...]] = (
    SourceRecord(
        name="fleurs",
        reference="google/fleurs",
        language="multi",
        license="CC-BY-4.0",
        license_verified_on="2026-08-11",
        license_source_url="https://huggingface.co/datasets/google/fleurs",
        commercial=CommercialVerdict.YES,
        access=Access.OPEN,
        speaker_ids=False,
        official_splits=True,
        contamination_risk="known_overlap",
        notes=(
            "Read speech (FLoRes sentences). Train/dev/test official splits; "
            "authors describe splits as speaker-aware [CLAIM]. Widely used in "
            "public model training/benchmarks since 2022 — treat every FLEURS "
            "number as comparability, never as the primary product ruler."
        ),
    ),
    SourceRecord(
        name="indicvoices",
        reference="ai4bharat/IndicVoices",
        language="hi",
        license="CC-BY-4.0",
        license_verified_on="2026-08-11",
        license_source_url="https://huggingface.co/datasets/ai4bharat/IndicVoices",
        commercial=CommercialVerdict.YES,
        access=Access.GATED,
        access_detail=(
            "HF gated:auto. UNBLOCKED 2026-08-11: founder account accepted the "
            "terms; read token present on this machine (never committed). "
            "Ingest via the `ingest-hf` preset with the token discovered from "
            "the environment/HF token file."
        ),
        speaker_ids=True,
        official_splits=True,
        contamination_risk="possible",
        notes=(
            "APPROVED PRIMARY eval source (+ future train backbone); "
            "spontaneous-heavy. Schema verified 2026-08-11: speaker_id, "
            "verbatim/normalized transcripts, scenario/gender/age/district. "
            "hindi/valid = 5,530 rows (~518 MB); hindi/train = 445,160 rows "
            "(~49 GB, NOT ingested — 15D concern)."
        ),
    ),
    SourceRecord(
        name="kathbath",
        reference="ai4bharat/Kathbath",
        language="hi",
        license="CC0 (explicit waiver on card)",
        license_verified_on="2026-08-11",
        license_source_url="https://huggingface.co/datasets/ai4bharat/Kathbath",
        commercial=CommercialVerdict.YES,
        access=Access.GATED,
        access_detail=(
            "HF gated:auto. UNBLOCKED 2026-08-11 (terms accepted, token "
            "present). Ingestion deferred: audio ships as M4A (fname "
            "'…-f.m4a'), outside the WAV-only probe — a recorded adapter "
            "gap for 15D, not a partial ingest."
        ),
        speaker_ids=True,
        official_splits=True,
        contamination_risk="possible",
        notes=(
            "APPROVED train source (clean read speech; speaker_id int64, "
            "schema verified 2026-08-11). Role: training (15D)."
        ),
    ),
    SourceRecord(
        name="common-voice-hi",
        reference="Mozilla Common Voice Scripted 26.0 (hi)",
        language="hi",
        license="CC0 (+ Mozilla Data Collective terms: no re-hosting)",
        license_verified_on="2026-08-10",
        license_source_url="https://github.com/common-voice/cv-dataset",
        commercial=CommercialVerdict.YES,
        access=Access.BLOCKED,
        access_detail=(
            "Downloads moved exclusively to the Mozilla Data Collective; "
            "requires an MDC account. No account available this session."
        ),
        speaker_ids=True,
        official_splits=True,
        contamination_risk="known_overlap",
        notes="APPROVED train source; 54.32 validated hi hours in 26.0.",
    ),
    SourceRecord(
        name="lahaja",
        reference="ai4bharat/Lahaja",
        language="hi",
        license=(
            "MIT (HF card tag, 2026-08-11; an earlier page read reported "
            "CC-BY-4.0 — both recorded, either is permissive)"
        ),
        license_verified_on="2026-08-11",
        license_source_url="https://huggingface.co/datasets/ai4bharat/Lahaja",
        commercial=CommercialVerdict.YES,
        access=Access.GATED,
        access_detail=(
            "HF gated:auto. UNBLOCKED 2026-08-11 (terms accepted, token "
            "present). Preset `lahaja-test` exists; freeze deferred — the "
            "15C primary is IndicVoices, one ruler at a time."
        ),
        speaker_ids=True,
        official_splits=False,
        contamination_risk="none_known",
        notes=(
            "APPROVED dialect-diverse hi eval set (12.5 h, 132 speakers; "
            "sp_id + normalized/verbatim, schema verified 2026-08-11). "
            "Role: evaluation (secondary, future freeze)."
        ),
    ),
    SourceRecord(
        name="common-voice-zh-cn",
        reference="Mozilla Common Voice Scripted 26.0 (zh-CN test)",
        language="zh",
        license="CC0 (+ MDC terms)",
        license_verified_on="2026-08-11",
        license_source_url="https://github.com/common-voice/cv-dataset",
        commercial=CommercialVerdict.YES,
        access=Access.BLOCKED,
        access_detail="MDC account required (same as common-voice-hi).",
        speaker_ids=True,
        official_splits=True,
        contamination_risk="none_known",
        notes=(
            "APPROVED zh eval (26.0 test cut of 2026-06-12 post-dates most "
            "published models' training). FLEURS zh is the provisional stand-in."
        ),
    ),
    # ── M22: no-speech negatives (the silence-regression fix) ───────────
    SourceRecord(
        name="negatives-synthetic",
        reference="intelliai_datasets.negatives (generated in-repo)",
        language="zxx",
        license="synthetic — generated in-repo, no external rights attach",
        license_verified_on="2026-08-17",
        license_source_url="https://github.com/Sumit-Das06/IntelliAI-Platform",
        commercial=CommercialVerdict.YES,
        access=Access.OPEN,
        speaker_ids=False,
        official_splits=False,
        contamination_risk="none_known",
        notes=(
            "Deterministic seeded digital silence and low-level noise "
            "(M22 Phase 3): teaches `language None<asr_text>` on "
            "no-speech input — the exact emission the pinned base model "
            "produces and the serving adapter parses to an empty result."
        ),
    ),
    SourceRecord(
        name="negatives-indicvoices-derived",
        reference="ai4bharat/IndicVoices (derived near-silence segments)",
        language="zxx",
        license="CC-BY-4.0 (derivative of IndicVoices audio; attribution carries)",
        license_verified_on="2026-08-11",
        license_source_url="https://huggingface.co/datasets/ai4bharat/IndicVoices",
        commercial=CommercialVerdict.YES,
        access=Access.OPEN,
        access_detail="derived locally from already-ingested approved clips",
        speaker_ids=False,
        official_splits=False,
        contamination_risk="none_known",
        notes=(
            "Quietest ≥2.5 s windows cut deterministically from approved "
            "ingested IndicVoices Hindi clips (parent clip id recorded per "
            "candidate); real room tone rather than digital zero, so the "
            "no-speech lesson generalizes past exact silence."
        ),
    ),
)


def source(name: str) -> SourceRecord:
    """Look a source up by name; unknown sources are refused loudly."""
    for record in SOURCES:
        if record.name == name:
            return record
    known = ", ".join(sorted(r.name for r in SOURCES))
    msg = f"unknown source {name!r}; registered: {known}"
    raise KeyError(msg)


def usable_now(record: SourceRecord) -> bool:
    """A source may feed ingestion only if open AND commercially usable."""
    return record.access is Access.OPEN and record.commercial is CommercialVerdict.YES
