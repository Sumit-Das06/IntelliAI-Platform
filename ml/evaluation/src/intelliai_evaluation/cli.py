"""Command-line interface for the evaluation seed (printing is this module's job)."""

from __future__ import annotations

import argparse
from pathlib import Path

from intelliai_evaluation.dataset import load_dataset
from intelliai_evaluation.fetch import materialize


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="intelliai-evaluation",
        description="Materialize versioned evaluation datasets (download + verify + synthesize).",
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

    args = parser.parse_args(argv)

    dataset = load_dataset(args.dataset)
    paths = materialize(dataset, args.data_dir)
    print(f"{dataset.name}@v{dataset.version}: {len(paths)} clips materialized")
    for clip_id, path in sorted(paths.items()):
        print(f"  {clip_id:<16} {path}")
    return 0
