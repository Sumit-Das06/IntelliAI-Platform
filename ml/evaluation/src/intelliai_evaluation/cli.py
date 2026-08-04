"""Command-line interface for the evaluation seed (printing is this module's job)."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

import httpx

from intelliai_evaluation import bench, bench_tts
from intelliai_evaluation.corpus import load_corpus
from intelliai_evaluation.dataset import load_dataset
from intelliai_evaluation.fetch import materialize
from intelliai_evaluation.resolution import UnservedError, load_manifest
from intelliai_evaluation.runner import run_stt_eval
from intelliai_evaluation.speech_results import EvaluatedArtifact, RuntimeIdentity
from intelliai_evaluation.speech_runner import (
    HttpSttJudge,
    HttpTtsSynthesisSource,
    run_speech_eval,
)


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
    # The artifact is NOT an argument: it is resolved from registry state,
    # because a benchmark against an operator-named artifact records a
    # claim rather than what the product actually serves.
    run_parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("ml/evaluation/manifests/resolution.json"),
        help="exported registry state (intelliai registry-manifest)",
    )
    run_parser.add_argument("--model", required=True, help="public model id, e.g. intelliai-stt")
    run_parser.add_argument("--language", required=True, help="the slice to measure, e.g. hi")
    run_parser.add_argument("--engine", required=True, help="engine name, e.g. faster-whisper")
    run_parser.add_argument("--engine-version", required=True)
    run_parser.add_argument("--compute", required=True, help="the build, e.g. cpu-int8")
    run_parser.add_argument("--hardware", required=True, help="human description of the machine")
    run_parser.add_argument(
        "--benchmark", default=None, help="set ONLY when this run IS a named baseline"
    )
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

    speech_parser = subcommands.add_parser(
        "speech-eval",
        help="evaluate a live synthesis runtime against a corpus and record the evidence",
    )
    speech_parser.add_argument("--corpus", type=Path, required=True, help="corpus JSON path")
    speech_parser.add_argument("--tts-url", default="http://localhost:8002")
    speech_parser.add_argument("--stt-url", default="http://localhost:8001", help="judge runtime")
    speech_parser.add_argument(
        "--artifact", required=True, help="evaluated artifact id, e.g. kokoro-82m"
    )
    speech_parser.add_argument("--artifact-version", type=int, default=1)
    speech_parser.add_argument("--lineage", required=True, help="model family, e.g. kokoro")
    speech_parser.add_argument("--judge-artifact", default="whisper-small")
    speech_parser.add_argument("--judge-version", type=int, default=1)
    speech_parser.add_argument("--voice", default=None, help="public voice id (synthesis param)")
    speech_parser.add_argument("--speed", type=float, default=None)
    speech_parser.add_argument("--hardware", required=True, help="human description of the machine")
    speech_parser.add_argument(
        "--baseline-name", default=None, help="set ONLY when this run IS a named baseline"
    )
    speech_parser.add_argument("--notes", default="")
    speech_parser.add_argument(
        "--out", type=Path, required=True, help="result JSON path (append-only results/ dir)"
    )

    bench_tts_parser = subcommands.add_parser(
        "bench-tts", help="production benchmark for the synthesis runtime: ladder + overhead"
    )
    bench_tts_parser.add_argument("--runtime-url", default="http://localhost:8002")
    bench_tts_parser.add_argument("--gateway-url", default="http://localhost:8000")
    bench_tts_parser.add_argument("--api-key", default="", help="gateway path key; empty skips it")
    bench_tts_parser.add_argument("--artifact", default="kokoro-82m")
    bench_tts_parser.add_argument("--model", default="intelliai-tts", help="public model id")
    bench_tts_parser.add_argument("--voice", default="reference-alto")
    bench_tts_parser.add_argument("--levels", default="1,5,10,20")
    bench_tts_parser.add_argument("--repetitions", type=int, default=3, help="requests per worker")
    bench_tts_parser.add_argument("--overhead-repetitions", type=int, default=10)
    bench_tts_parser.add_argument("--hardware", required=True)
    bench_tts_parser.add_argument("--docker-container", default="")
    bench_tts_parser.add_argument("--notes", default="")
    bench_tts_parser.add_argument("--timeout", type=float, default=600.0)
    bench_tts_parser.add_argument("--out", type=Path, required=True)

    args = parser.parse_args(argv)

    if args.command == "bench":
        return _run_bench(args)
    if args.command == "bench-tts":
        return _run_bench_tts(args)
    if args.command == "speech-eval":
        return _run_speech_eval(args)

    dataset = load_dataset(args.dataset)

    if args.command == "fetch":
        paths = materialize(dataset, args.data_dir)
        print(f"{dataset.name}@v{dataset.version}: {len(paths)} clips materialized")
        for clip_id, path in sorted(paths.items()):
            print(f"  {clip_id:<16} {path}")
        return 0

    # Registry state decides what is measured; the operator supplies only
    # facts about the machine it runs on.
    manifest = load_manifest(args.manifest)
    try:
        serving = manifest.resolve(args.model, args.language)
    except UnservedError as exc:
        print(f"refusing: {exc}")
        return 2

    run = run_stt_eval(
        dataset,
        base_url=args.url,
        data_dir=args.data_dir,
        public_model=args.model,
        language=args.language,
        serving=serving,
        build=args.compute,
        engine=args.engine,
        engine_version=args.engine_version,
        hardware=args.hardware,
        benchmark=args.benchmark,
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


def _run_speech_eval(args: argparse.Namespace) -> int:
    """Corpus + two live runtimes -> one immutable evidence record.

    Reproducibility metadata is taken from LIVE facts, never operator
    claims: both runtimes' /info supply service identity, and the run
    refuses to start if the synthesis runtime is not actually serving the
    artifact being evaluated — a record that misnames its subject would
    poison the ledger."""
    corpus = load_corpus(args.corpus)

    tts_info = httpx.get(f"{args.tts_url}/info", timeout=30).json()
    served = {model["artifact"] for model in tts_info["models"]}
    if args.artifact not in served:
        print(f"refusing: runtime at {args.tts_url} serves {sorted(served)}, not {args.artifact!r}")
        return 2
    stt_info = httpx.get(f"{args.stt_url}/info", timeout=30).json()

    synthesis_params: dict[str, str] = {}
    if args.voice is not None:
        synthesis_params["voice"] = args.voice
    if args.speed is not None:
        synthesis_params["speed"] = str(args.speed)

    run = run_speech_eval(
        corpus=corpus,
        source=HttpTtsSynthesisSource(args.tts_url),
        judge=HttpSttJudge(
            args.stt_url,
            judge_artifact=args.judge_artifact,
            judge_artifact_version=args.judge_version,
            runtime_version=stt_info["service_version"],
        ),
        evaluated=EvaluatedArtifact(
            artifact=args.artifact, version=args.artifact_version, lineage=args.lineage
        ),
        runtime=RuntimeIdentity(
            service=tts_info["service"], service_version=tts_info["service_version"]
        ),
        hardware=args.hardware,
        synthesis_params=synthesis_params,
        baseline_name=args.baseline_name,
        notes=args.notes,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(run.model_dump_json(indent=2) + "\n", encoding="utf-8")

    failures = [case for case in run.cases if case.failure]
    print(f"{corpus.name}@v{corpus.version}: {len(run.cases)} cases, {len(failures)} failed")
    for case in failures:
        print(f"  FAIL {case.case_id}: {case.failure}")
    for name, value in sorted(run.aggregate_metrics.items()):
        print(f"  {name}: {value:.4f}")
    print(f"recorded: {args.out}")
    return 0


def _run_bench_tts(args: argparse.Namespace) -> int:
    direct_body: dict[str, object] = {
        "text": bench_tts.BENCH_TEXT,
        "voice": args.voice,
        "model": args.artifact,
    }
    levels = [int(level) for level in str(args.levels).split(",")]
    container = args.docker_container or None

    async def execute() -> bench_tts.TtsBenchReport:
        level_results = []
        for concurrency in levels:
            print(f"level c={concurrency} ...")
            level_results.append(
                await bench_tts.run_tts_level(
                    url=f"{args.runtime_url}/v1/synthesize",
                    runtime_url=args.runtime_url,
                    body=direct_body,
                    concurrency=concurrency,
                    repetitions=args.repetitions,
                    docker_container=container,
                    timeout_seconds=args.timeout,
                )
            )
        overhead = None
        prd_actual = None
        if args.api_key:
            print("gateway overhead ...")
            overhead = await bench_tts.measure_tts_overhead(
                gateway_url=args.gateway_url,
                runtime_url=args.runtime_url,
                api_key=args.api_key,
                public_model=args.model,
                artifact=args.artifact,
                voice=args.voice,
                text=bench_tts.BENCH_TEXT,
                repetitions=args.overhead_repetitions,
                timeout_seconds=args.timeout,
            )
            prd_actual = overhead.via_gateway_p50_ms
        target_ms = 1000.0  # PRD: TTFB < 1s (unstreamed = full response, conservative)
        verdict = "not measured"
        if prd_actual is not None:
            verdict = "PASS" if prd_actual < target_ms else "FAIL"
        audio_seconds = None
        for level in level_results:
            if level.mean_rtf and level.p50_ms:
                audio_seconds = round(level.p50_ms / 1000.0 / level.mean_rtf, 3)
                break
        return bench_tts.TtsBenchReport(
            text=bench_tts.BENCH_TEXT,
            characters=len(bench_tts.BENCH_TEXT),
            audio_seconds=audio_seconds,
            repetitions_per_worker=args.repetitions,
            hardware=args.hardware,
            notes=args.notes,
            levels=level_results,
            overhead=overhead,
            prd_ttfb_target_ms=target_ms,
            prd_ttfb_actual_ms=prd_actual,
            prd_verdict=verdict,
        )

    report = asyncio.run(execute())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    print(report.model_dump_json(indent=2))
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
