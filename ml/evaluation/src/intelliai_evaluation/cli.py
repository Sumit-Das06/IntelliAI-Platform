"""Command-line interface for the evaluation seed (printing is this module's job)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from intelliai_evaluation.dataset import load_dataset
from intelliai_evaluation.fetch import materialize
from intelliai_evaluation.runner import run_stt_eval


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="intelliai-evaluation",
        description="Materialize datasets and measure live runtimes against them.",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    fetch_parser = subcommands.add_parser("fetch", help="materialize a dataset's clips locally")
    fetch_parser.add_argument("--dataset", type=Path, required=True, help="manifest JSON path")
    fetch_parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("ml/evaluation/data"),
        help="local clip cache (gitignored; default: ml/evaluation/data)",
    )

    run_parser = subcommands.add_parser(
        "run", help="evaluate a live runtime against a dataset and record the results"
    )
    run_parser.add_argument("--dataset", type=Path, required=True, help="manifest JSON path")
    run_parser.add_argument("--data-dir", type=Path, default=Path("ml/evaluation/data"))
    run_parser.add_argument("--url", default="http://localhost:8001", help="runtime base URL")
    run_parser.add_argument("--artifact", required=True, help="artifact id, e.g. whisper-small")
    run_parser.add_argument("--engine", required=True, help="engine name, e.g. faster-whisper")
    run_parser.add_argument("--engine-version", required=True)
    run_parser.add_argument("--compute", required=True, help="e.g. cpu-int8")
    run_parser.add_argument("--hardware", required=True, help="human description of the machine")
    run_parser.add_argument("--notes", default="")
    run_parser.add_argument(
        "--out", type=Path, required=True, help="result JSON path (append-only results/ dir)"
    )

    args = parser.parse_args(argv)
    dataset = load_dataset(args.dataset)

    if args.command == "fetch":
        paths = materialize(dataset, args.data_dir)
        print(f"{dataset.name}@v{dataset.version}: {len(paths)} clips materialized")
        for clip_id, path in sorted(paths.items()):
            print(f"  {clip_id:<16} {path}")
        return 0

    run = run_stt_eval(
        dataset,
        base_url=args.url,
        data_dir=args.data_dir,
        artifact=args.artifact,
        engine=args.engine,
        engine_version=args.engine_version,
        compute=args.compute,
        hardware=args.hardware,
        notes=args.notes,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(run.model_dump_json(indent=2) + "\n", encoding="utf-8")
    print(json.dumps(run.summary(), indent=2, default=str))
    for clip in run.clips:
        wer = "n/a" if clip.wer is None else f"{clip.wer:.3f}"
        print(
            f"  {clip.clip_id:<16} wer={wer:<6} rtf={clip.rtf:.3f} "
            f"hallucinated={clip.hallucinated_words}"
        )
    print(f"recorded: {args.out}")
    return 0
