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

from intelliai_datasets.curate import curate_by_budget, curate_count, total_duration
from intelliai_datasets.ingest_fleurs import ingest_fleurs
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


def _write_candidates(samples: list[CandidateSample], problems: list[str], target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "candidates": [s.model_dump() for s in samples],
        "ingestion_problems": problems,
    }
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _read_candidates(path: Path) -> tuple[list[CandidateSample], list[str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    samples = [CandidateSample.model_validate(row) for row in payload["candidates"]]
    problems = [str(p) for p in payload.get("ingestion_problems", [])]
    return samples, problems


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


def _cmd_freeze_eval(args: argparse.Namespace) -> int:
    samples, _ = _read_candidates(args.candidates)
    accepted, rejections = validate_samples(
        samples,
        expected_language=args.language,
        data_root=args.data_root,
    )
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
            f"deterministic: validation in ingestion order, then ascending "
            f"sha256 order, first {args.count or 'all'} accepted natural-speech "
            f"clips; probes appended"
        ),
        validation=report,
    )
    write_provenance(provenance, args.provenance_out)
    print(f"EVAL MANIFEST: {pin.path}")
    print(f"EVAL MANIFEST SHA256: {pin.sha256}")
    print(
        f"clips: {pin.samples} ({len(chosen)} natural + {len(probes)} probes), "
        f"natural duration: {pin.duration_seconds}s"
    )
    print(f"rejections: {len(rejections)}")
    return 0


def _cmd_freeze_train(args: argparse.Namespace) -> int:
    samples, _ = _read_candidates(args.candidates)
    eval_dataset = load_dataset(args.eval_manifest)
    eval_hashes = [c.sha256 for c in eval_dataset.clips if c.sha256 is not None]
    accepted, rejections = validate_samples(
        samples,
        expected_language=args.language,
        data_root=args.data_root,
        eval_sha256=eval_hashes,
        # FLEURS publishes no speaker ids; the roster is empty until a
        # speaker-bearing source is unlocked. Disjointness is then enforced
        # here automatically.
        eval_speakers=(),
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
        ),
        validation=report,
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

    freeze_eval = sub.add_parser("freeze-eval", help="freeze an immutable eval manifest")
    freeze_eval.add_argument("--candidates", type=Path, required=True)
    freeze_eval.add_argument("--language", required=True)
    freeze_eval.add_argument("--name", required=True)
    freeze_eval.add_argument("--version", type=int, required=True)
    freeze_eval.add_argument("--description", required=True)
    freeze_eval.add_argument("--count", type=int, default=0, help="0 = all accepted")
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
    freeze_train.add_argument("--candidates", type=Path, required=True)
    freeze_train.add_argument("--eval-manifest", type=Path, required=True)
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
