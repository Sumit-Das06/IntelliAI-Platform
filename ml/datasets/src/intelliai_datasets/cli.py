"""CLI: ingest → validate → curate → freeze, each step deterministic.

Verbs:

- ``ingest-fleurs`` — download + extract one (config, split) into the
  data root; write the candidates file (the raw ingestion record).
- ``freeze-eval`` — validate + curate candidates into an immutable
  EvalDataset manifest (+ provenance sidecar); print the pin.
- ``freeze-train`` — validate candidates AGAINST a frozen eval manifest
  (contamination + speaker disjointness), curate to a duration budget,
  write the platform-format JSONL (+ provenance sidecar); print the pin.

The eval freeze exists before the train freeze can run: ``freeze-train``
requires the frozen eval manifest as an input. That ordering is the law
("evaluation before training counterparts"), enforced by the tool shape.
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path

from intelliai_datasets.curate import (
    curate_by_budget,
    curate_count,
    curate_speakers,
    speaker_roster,
    total_duration,
)
from intelliai_datasets.hf import HfAccessError, discover_token
from intelliai_datasets.ingest_fleurs import ingest_fleurs
from intelliai_datasets.ingest_hf import SPECS, ingest_hf
from intelliai_datasets.manifests import (
    HI_PROBES,
    ZH_PROBES,
    Provenance,
    build_eval_dataset,
    write_eval_dataset,
    write_provenance,
    write_train_jsonl,
)
from intelliai_datasets.samples import CandidateSample
from intelliai_datasets.sources import SOURCES, source, usable_now
from intelliai_datasets.validate import ValidationReport, validate_samples
from intelliai_evaluation.dataset import load_dataset

_PROBES = {"hi": HI_PROBES, "zh": ZH_PROBES}


def _write_candidates(
    samples: list[CandidateSample],
    problems: list[str],
    target: Path,
    *,
    revision: str = "",
) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "source_revision": revision,
        "candidates": [s.model_dump() for s in samples],
        "ingestion_problems": problems,
    }
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _read_candidates(path: Path) -> tuple[list[CandidateSample], list[str], str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    samples = [CandidateSample.model_validate(row) for row in payload["candidates"]]
    problems = [str(p) for p in payload.get("ingestion_problems", [])]
    return samples, problems, str(payload.get("source_revision", ""))


def _statistics(samples: list[CandidateSample]) -> dict[str, dict[str, int]]:
    """Descriptive stats for provenance — counted, never invented."""
    styles: dict[str, int] = {}
    genders: dict[str, int] = {}
    durations: dict[str, int] = {}
    text_lengths: dict[str, int] = {}
    per_source: dict[str, int] = {}
    for sample in samples:
        note = sample.notes
        style = _note_field(note, "scenario") or "unknown"
        gender = _note_field(note, "gender") or "unknown"
        styles[style] = styles.get(style, 0) + 1
        genders[gender] = genders.get(gender, 0) + 1
        band = (
            "<5s"
            if sample.duration_seconds < 5
            else "5-15s"
            if sample.duration_seconds < 15
            else "15-30s"
        )
        durations[band] = durations.get(band, 0) + 1
        words = len(sample.text.split())
        text_band = "<10w" if words < 10 else "10-25w" if words < 25 else ">=25w"
        text_lengths[text_band] = text_lengths.get(text_band, 0) + 1
        per_source[sample.source] = per_source.get(sample.source, 0) + 1
    return {
        "style": styles,
        "gender": genders,
        "duration_bands": durations,
        "transcript_length_bands": text_lengths,
        "source": per_source,
    }


def _note_field(notes: str, field: str) -> str | None:
    marker = f"{field}="
    if marker not in notes:
        return None
    value = notes.split(marker, 1)[1].split(" ", 1)[0]
    return value.strip("'\"") or None


def _cmd_ingest_fleurs(args: argparse.Namespace) -> int:
    record = source("fleurs")
    if not usable_now(record):
        print(f"refusing: source fleurs is {record.access}/{record.commercial}")
        return 2
    samples, problems = ingest_fleurs(
        config=args.config,
        split=args.split,
        data_root=args.data_root,
        max_rows=args.max_rows,
    )
    _write_candidates(samples, problems, args.out)
    print(f"ingested {len(samples)} candidates ({len(problems)} row problems) -> {args.out}")
    return 0


def _cmd_ingest_hf(args: argparse.Namespace) -> int:
    spec = SPECS.get(args.preset)
    if spec is None:
        print(f"unknown preset {args.preset!r}; known: {', '.join(sorted(SPECS))}")
        return 2
    if discover_token() is None:
        print(
            "BLOCKED: no Hugging Face token found (HF_TOKEN env or "
            "~/.cache/huggingface/token). Gated sources cannot be fetched; "
            "nothing was faked."
        )
        return 2
    try:
        result = ingest_hf(
            spec,
            data_root=args.data_root,
            max_rows=args.max_rows,
            max_shards=args.max_shards,
        )
    except HfAccessError as exc:
        print(f"BLOCKED: {exc}")
        return 2
    _write_candidates(
        list(result.samples),
        list(result.problems),
        args.out,
        revision=result.revision,
    )
    print(
        f"ingested {len(result.samples)} candidates "
        f"({len(result.problems)} row problems) from {spec.hf_id}@{result.revision[:12]} "
        f"-> {args.out}"
    )
    return 0


def _cmd_freeze_eval(args: argparse.Namespace) -> int:
    samples, _, revision = _read_candidates(args.candidates)
    accepted, rejections = validate_samples(
        samples,
        expected_language=args.language,
        data_root=args.data_root,
        require_speaker_ids=args.speaker_mode,
    )
    if args.speaker_mode:
        chosen = curate_speakers(
            accepted,
            target_clips=args.count or 150,
            max_per_speaker=args.max_per_speaker,
        )
    else:
        chosen = curate_count(accepted, count=args.count) if args.count else accepted
    report = ValidationReport(
        source=",".join(sorted({s.source for s in samples})) or "none",
        language=args.language,
        split=",".join(sorted({s.split for s in samples})) or "none",
        candidates=len(samples),
        accepted=len(accepted),
        rejections=tuple(rejections),
        accepted_duration_seconds=round(total_duration(accepted), 3),
    )
    probes = _PROBES.get(args.language, ())
    dataset = build_eval_dataset(
        chosen,
        name=args.name,
        version=args.version,
        description=args.description,
        probes=probes,
    )
    pin = write_eval_dataset(dataset, args.out)
    roster = speaker_roster(chosen) if args.speaker_mode else ()
    curation_recipe = (
        (
            f"deterministic speaker-grouped: whole speakers in ascending "
            f"sha256(speaker_id) order, <= {args.max_per_speaker} clips each "
            f"(clip order = ascending clip sha256), until >= "
            f"{args.count or 150} clips; probes appended"
        )
        if args.speaker_mode
        else (
            f"deterministic: validation in ingestion order, then ascending "
            f"sha256 order, first {args.count or 'all'} accepted natural-speech "
            f"clips; probes appended"
        )
    )
    provenance = Provenance(
        manifest=pin,
        created=args.created,
        language=args.language,
        sources=tuple(source(name) for name in sorted({s.source for s in chosen})),
        source_splits=tuple(sorted({s.split for s in chosen})),
        normalization="unicode_generic@v2",
        primary_ruler="cer_unicode",
        contamination_risk=args.contamination_risk,
        speaker_ids_available=all(s.speaker_id is not None for s in chosen) and bool(chosen),
        speaker_disjointness=args.speaker_disjointness,
        curation=curation_recipe,
        validation=report,
        source_revisions={s: revision for s in {c.source for c in chosen} if revision},
        speaker_roster=roster,
        statistics=_statistics(chosen),
    )
    write_provenance(provenance, args.provenance_out)
    print(f"EVAL MANIFEST: {pin.path}")
    print(f"EVAL MANIFEST SHA256: {pin.sha256}")
    if args.speaker_mode:
        print(f"speakers in roster: {len(roster)}")
    print(
        f"clips: {pin.samples} ({len(chosen)} natural + {len(probes)} probes), "
        f"natural duration: {pin.duration_seconds}s"
    )
    print(f"rejections: {len(rejections)}")
    return 0


def _cmd_freeze_train(args: argparse.Namespace) -> int:
    samples: list[CandidateSample] = []
    revisions: dict[str, str] = {}
    for candidates_path in args.candidates:
        file_samples, _, revision = _read_candidates(candidates_path)
        samples.extend(file_samples)
        for s_ in file_samples:
            if revision:
                revisions[s_.source] = revision
    eval_dataset = load_dataset(args.eval_manifest)
    eval_hashes = [c.sha256 for c in eval_dataset.clips if c.sha256 is not None]
    # The frozen eval's speaker roster (recorded in its provenance sidecar)
    # is the disjointness enforcement input: any candidate by a roster
    # speaker is rejected here, mechanically.
    eval_speakers: tuple[str, ...] = ()
    if args.eval_provenance is not None and args.eval_provenance.exists():
        sidecar = json.loads(args.eval_provenance.read_text(encoding="utf-8"))
        eval_speakers = tuple(str(s) for s in sidecar.get("speaker_roster", ()))
    accepted, rejections = validate_samples(
        samples,
        expected_language=args.language,
        data_root=args.data_root,
        eval_sha256=eval_hashes,
        eval_speakers=eval_speakers,
    )
    chosen = curate_by_budget(
        accepted,
        target_duration_seconds=args.target_hours * 3600.0,
    )
    report = ValidationReport(
        source=",".join(sorted({s.source for s in samples})) or "none",
        language=args.language,
        split=",".join(sorted({s.split for s in samples})) or "none",
        candidates=len(samples),
        accepted=len(accepted),
        rejections=tuple(rejections),
        accepted_duration_seconds=round(total_duration(accepted), 3),
    )
    pin = write_train_jsonl(chosen, args.out)
    provenance = Provenance(
        manifest=pin,
        created=args.created,
        language=args.language,
        sources=tuple(source(name) for name in sorted({s.source for s in chosen})),
        source_splits=tuple(sorted({s.split for s in chosen})),
        normalization="unicode_generic@v2",
        primary_ruler="cer_unicode",
        contamination_risk=args.contamination_risk,
        speaker_ids_available=all(s.speaker_id is not None for s in chosen) and bool(chosen),
        speaker_disjointness=args.speaker_disjointness,
        curation=(
            f"deterministic: ascending sha256 order until "
            f"{args.target_hours}h budget met (first crossing clip included); "
            f"eval disjointness enforced by content hash against "
            f"{eval_dataset.name}@v{eval_dataset.version}"
            + (f" and by speaker roster ({len(eval_speakers)} speakers)" if eval_speakers else "")
        ),
        validation=report,
        source_revisions={
            s_: r for s_, r in revisions.items() if any(c.source == s_ for c in chosen)
        },
        statistics=_statistics(chosen),
    )
    write_provenance(provenance, args.provenance_out)
    print(f"TRAIN MANIFEST: {pin.path}")
    print(f"TRAIN MANIFEST SHA256: {pin.sha256}")
    print(f"samples: {pin.samples}, duration: {pin.duration_seconds}s")
    print(f"rejections: {len(rejections)}")
    return 0


def _cmd_sources(_: argparse.Namespace) -> int:
    for record in SOURCES:
        print(
            f"{record.name}: license={record.license!r} "
            f"(verified {record.license_verified_on}) "
            f"commercial={record.commercial} access={record.access}"
            + (f" — {record.access_detail}" if record.access_detail else "")
        )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="intelliai-datasets")
    sub = parser.add_subparsers(dest="command", required=True)

    today = datetime.datetime.now(tz=datetime.UTC).date().isoformat()

    ingest = sub.add_parser("ingest-fleurs", help="ingest one FLEURS (config, split)")
    ingest.add_argument("--config", required=True)
    ingest.add_argument("--split", required=True)
    ingest.add_argument("--data-root", type=Path, default=Path("ml/datasets/data"))
    ingest.add_argument("--max-rows", type=int, default=None)
    ingest.add_argument("--out", type=Path, required=True)
    ingest.set_defaults(func=_cmd_ingest_fleurs)

    ingest_gated = sub.add_parser(
        "ingest-hf", help="ingest a registered gated/open HF dataset preset"
    )
    ingest_gated.add_argument("--preset", required=True, help=", ".join(sorted(SPECS)))
    ingest_gated.add_argument("--data-root", type=Path, default=Path("ml/datasets/data"))
    ingest_gated.add_argument("--max-rows", type=int, default=None)
    ingest_gated.add_argument(
        "--max-shards",
        type=int,
        default=None,
        help="deterministic prefix of the sorted shard list (huge-split sampling)",
    )
    ingest_gated.add_argument("--out", type=Path, required=True)
    ingest_gated.set_defaults(func=_cmd_ingest_hf)

    freeze_eval = sub.add_parser("freeze-eval", help="freeze an immutable eval manifest")
    freeze_eval.add_argument("--candidates", type=Path, required=True)
    freeze_eval.add_argument("--language", required=True)
    freeze_eval.add_argument("--name", required=True)
    freeze_eval.add_argument("--version", type=int, required=True)
    freeze_eval.add_argument("--description", required=True)
    freeze_eval.add_argument("--count", type=int, default=0, help="0 = all accepted")
    freeze_eval.add_argument(
        "--speaker-mode",
        action="store_true",
        help="whole-speaker curation; requires speaker ids; freezes the roster",
    )
    freeze_eval.add_argument("--max-per-speaker", type=int, default=8)
    freeze_eval.add_argument("--data-root", type=Path, default=Path("ml/datasets/data"))
    freeze_eval.add_argument("--out", type=Path, required=True)
    freeze_eval.add_argument("--provenance-out", type=Path, required=True)
    freeze_eval.add_argument("--contamination-risk", default="known_overlap")
    freeze_eval.add_argument(
        "--speaker-disjointness",
        default=(
            "UNPROVABLE from this source: no per-clip speaker ids published; "
            "train/eval separation relies on the source's official split "
            "boundary (publisher claim, not our verification)."
        ),
    )
    freeze_eval.add_argument("--created", default=today)
    freeze_eval.set_defaults(func=_cmd_freeze_eval)

    freeze_train = sub.add_parser("freeze-train", help="freeze a train JSONL manifest")
    freeze_train.add_argument("--candidates", type=Path, required=True, nargs="+")
    freeze_train.add_argument("--eval-manifest", type=Path, required=True)
    freeze_train.add_argument(
        "--eval-provenance",
        type=Path,
        default=None,
        help="frozen eval's provenance sidecar; its speaker_roster is enforced",
    )
    freeze_train.add_argument("--language", required=True)
    freeze_train.add_argument("--target-hours", type=float, required=True)
    freeze_train.add_argument("--data-root", type=Path, default=Path("ml/datasets/data"))
    freeze_train.add_argument("--out", type=Path, required=True)
    freeze_train.add_argument("--provenance-out", type=Path, required=True)
    freeze_train.add_argument("--contamination-risk", default="known_overlap")
    freeze_train.add_argument(
        "--speaker-disjointness",
        default=(
            "UNPROVABLE from this source: no per-clip speaker ids published; "
            "content-hash disjointness against the frozen eval IS enforced."
        ),
    )
    freeze_train.add_argument("--created", default=today)
    freeze_train.set_defaults(func=_cmd_freeze_train)

    sources_cmd = sub.add_parser("sources", help="print the source registry")
    sources_cmd.set_defaults(func=_cmd_sources)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result: int = args.func(args)
    return result


if __name__ == "__main__":
    sys.exit(main())
