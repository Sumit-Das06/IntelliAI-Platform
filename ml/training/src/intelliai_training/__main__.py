"""CLI: smoke -> train -> merge, each step an explicit decision."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from intelliai_training.config import TrainingConfig
from intelliai_training.manifest import sha256_file


def _config_from_args(args: argparse.Namespace) -> TrainingConfig:
    manifest = Path(args.manifest)
    return TrainingConfig(
        experiment=args.experiment,
        base_revision=args.base_revision,
        manifest_path=manifest.as_posix(),
        manifest_sha256=args.manifest_sha or sha256_file(manifest),
        max_steps=args.max_steps,
        per_device_batch_size=args.batch_size,
        gradient_accumulation=args.grad_accum,
        learning_rate=args.learning_rate,
        warmup_steps=args.warmup_steps,
        checkpoint_every_steps=args.checkpoint_every,
        output_dir=args.output_dir,
        seed=args.seed,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="intelliai-training")
    sub = parser.add_subparsers(dest="command", required=True)

    for name in ("smoke", "train"):
        p = sub.add_parser(name)
        p.add_argument("--manifest", required=True)
        p.add_argument("--manifest-sha", default=None)
        p.add_argument("--base-revision", required=True)
        p.add_argument("--max-steps", type=int, default=4000)
        p.add_argument("--batch-size", type=int, default=8)
        p.add_argument("--grad-accum", type=int, default=4)
        p.add_argument("--learning-rate", type=float, default=1e-3)
        p.add_argument("--warmup-steps", type=int, default=100)
        p.add_argument("--checkpoint-every", type=int, default=500)
        p.add_argument("--experiment", default="e1-hi-lora")
        p.add_argument("--output-dir", default="weights/e1-hi-lora")
        p.add_argument("--seed", type=int, default=20260811)
        p.add_argument("--out", required=True, help="report/record JSON path")

    merge = sub.add_parser("merge")
    merge.add_argument("--config", required=True, help="the run's config.json")
    merge.add_argument("--checkpoint", required=True)
    merge.add_argument("--merged-dir", required=True)
    merge.add_argument("--ct2-dir", required=True)

    args = parser.parse_args(argv)

    if args.command in ("smoke", "train"):
        from intelliai_training.trainer import run

        result = run(_config_from_args(args), smoke=args.command == "smoke")
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(result.model_dump_json(indent=2) + "\n", encoding="utf-8")
        print(f"written: {out}")
        return 0

    from intelliai_training.merge import convert_to_ct2, merge_adapter

    config = TrainingConfig.model_validate_json(Path(args.config).read_text(encoding="utf-8"))
    merge_adapter(config, Path(args.checkpoint), Path(args.merged_dir))
    pins = convert_to_ct2(Path(args.merged_dir), Path(args.ct2_dir))
    print(f"merged + converted; {len(pins)} files pinned (artifact-pins.json)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
