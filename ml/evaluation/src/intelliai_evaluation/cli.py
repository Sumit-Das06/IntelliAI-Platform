"""Command-line interface for the evaluation seed (printing is this module's job)."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from intelliai_evaluation import bench
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

    bench_parser = subcommands.add_parser(
        "bench", help="production benchmark: concurrency sweep + gateway overhead"
    )
    bench_parser.add_argument("--clip", type=Path, required=True, help="pinned WAV clip")
    bench_parser.add_argument("--runtime-url", default="http://localhost:8001")
    bench_parser.add_argument("--gateway-url", default="http://localhost:8000")
    bench_parser.add_argument("--api-key", default="", help="gateway path key; empty skips it")
    bench_parser.add_argument("--artifact", default="whisper-small")
    bench_parser.add_argument("--model", default="intelliai-stt", help="public model id")
    bench_parser.add_argument("--levels", default="1,5,10,20")
    bench_parser.add_argument("--repetitions", type=int, default=3, help="requests per worker")
    bench_parser.add_argument("--overhead-repetitions", type=int, default=10)
    bench_parser.add_argument("--hardware", required=True)
    bench_parser.add_argument("--docker-container", default="")
    bench_parser.add_argument("--notes", default="")
    bench_parser.add_argument("--timeout", type=float, default=600.0)
    bench_parser.add_argument("--out", type=Path, required=True)

    args = parser.parse_args(argv)

    if args.command == "bench":
        return _run_bench(args)

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


def _run_bench(args: argparse.Namespace) -> int:
    audio = args.clip.read_bytes()
    clip_seconds = bench.clip_duration_seconds(args.clip)
    direct_params = {"params": json.dumps({"model": args.artifact})}
    levels = [int(level) for level in str(args.levels).split(",")]
    container = args.docker_container or None

    async def execute() -> bench.BenchReport:
        level_results = []
        for concurrency in levels:
            print(f"level c={concurrency} ...")
            level_results.append(
                await bench.run_level(
                    url=f"{args.runtime_url}/v1/transcribe",
                    runtime_url=args.runtime_url,
                    audio=audio,
                    params=direct_params,
                    concurrency=concurrency,
                    repetitions=args.repetitions,
                    clip_seconds=clip_seconds,
                    docker_container=container,
                    timeout_seconds=args.timeout,
                )
            )
        overhead = None
        prd_actual = None
        if args.api_key:
            print("gateway overhead ...")
            overhead = await bench.measure_overhead(
                gateway_url=args.gateway_url,
                runtime_url=args.runtime_url,
                api_key=args.api_key,
                public_model=args.model,
                artifact=args.artifact,
                audio=audio,
                repetitions=args.overhead_repetitions,
                timeout_seconds=args.timeout,
            )
            prd_actual = overhead.via_gateway_p50_ms  # see note below
        target_ms = clip_seconds * 1500.0  # PRD: p95 < 1.5x audio duration
        verdict = "not measured"
        if overhead is not None:
            verdict = "PASS" if overhead.via_gateway_p50_ms < target_ms else "FAIL"
        return bench.BenchReport(
            clip=args.clip.name,
            clip_seconds=round(clip_seconds, 3),
            repetitions_per_worker=args.repetitions,
            hardware=args.hardware,
            notes=args.notes,
            levels=level_results,
            overhead=overhead,
            prd_p95_target_ms=round(target_ms, 1),
            prd_p95_actual_ms=prd_actual,
            prd_verdict=verdict,
        )

    report = asyncio.run(execute())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    print(report.model_dump_json(indent=2))
    print(f"recorded: {args.out}")
    return 0
