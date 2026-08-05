"""Production benchmark harness — the platform's performance ruler.

Deterministic methodology (M2 step 7, refinements 5-9):

- One pinned clip, N repetitions, fixed concurrency ladder. Every request
  is identical; every aggregate is computed the same way every run.
- Latency is measured at the CLIENT (wall clock around the HTTP call) and
  decomposed using the runtime envelope's own stage timings — the same
  numbers customers' requests carry.
- Gateway overhead = median(client latency via gateway) minus median(client
  latency direct to runtime), same clip, same repetitions (ADR-0002 check).
- Percentiles use nearest-rank on the sorted sample: no interpolation,
  no library variance — two runs of the same data agree to the digit.
- Saturation is part of the measurement: requests refused with
  `overloaded` are counted, never retried and never hidden.
- Optional `docker stats` sampling records container CPU/memory per level.

Results serialize to JSON (`BenchReport`); the permanent human-readable
baseline lives beside them in stt/benchmarks/.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import time
import wave
from pathlib import Path

import httpx

# The record types and the percentile function live in `evidence`, which
# imports nothing beyond pydantic and stdlib. This module needs httpx and
# shells out to `docker stats`, so leaving them here would mean reading a
# five-year-old committed ladder required an HTTP client to be
# installable. Re-exported so every existing import keeps working.
from intelliai_evaluation.evidence import (
    BenchReport,
    LevelResult,
    OverheadResult,
    RequestSample,
    nearest_rank,
)

__all__ = [
    "BenchReport",
    "DockerSampler",
    "LevelResult",
    "OverheadResult",
    "RequestSample",
    "clip_duration_seconds",
    "measure_overhead",
    "nearest_rank",
    "run_level",
]


def clip_duration_seconds(path: Path) -> float:
    with wave.open(str(path)) as reader:
        return float(reader.getnframes()) / float(reader.getframerate())


async def _one_request(
    client: httpx.AsyncClient,
    url: str,
    audio: bytes,
    params: dict[str, str],
    headers: dict[str, str] | None = None,
) -> RequestSample:
    started = time.perf_counter()
    try:
        response = await client.post(
            url,
            files={"file": ("bench.wav", audio, "audio/wav")},
            data=params,
            headers=headers or {},
        )
    except httpx.HTTPError:
        return RequestSample(ok=False, status=0, client_ms=(time.perf_counter() - started) * 1000)
    client_ms = (time.perf_counter() - started) * 1000
    if response.status_code != 200:
        return RequestSample(ok=False, status=response.status_code, client_ms=client_ms)
    stages: dict[str, float] = {}
    runtime_total: float | None = None
    try:
        body = response.json()
        timing = body.get("timing")
        if isinstance(timing, dict):  # direct-runtime envelope
            stages = {key: float(value) for key, value in timing.get("stages", {}).items()}
            raw_total = timing.get("total_ms")
            runtime_total = float(raw_total) if raw_total is not None else None
    except (ValueError, TypeError):
        pass
    return RequestSample(
        ok=True,
        status=200,
        client_ms=client_ms,
        runtime_total_ms=runtime_total,
        stages_ms=stages,
    )


class DockerSampler:
    """Max CPU%/memory of a container while a level runs (best effort)."""

    def __init__(self, container: str | None) -> None:
        self._container = container
        self.cpu_max: float | None = None
        self.mem_max: float | None = None

    def sample_once(self) -> None:
        if not self._container:
            return
        # Fixed argv, local docker CLI from PATH — benchmark tooling only.
        argv = ["docker", "stats", "--no-stream", "--format", "{{json .}}", self._container]
        completed = subprocess.run(  # noqa: S603
            argv,
            capture_output=True,
            timeout=20,
            check=False,
        )
        if completed.returncode != 0:
            return
        try:
            stats = json.loads(completed.stdout.decode("utf-8"))
            cpu = float(str(stats["CPUPerc"]).rstrip("%"))
            mem_text = str(stats["MemUsage"]).split("/")[0].strip()
            mem = _to_mib(mem_text)
        except (ValueError, KeyError):
            return
        self.cpu_max = cpu if self.cpu_max is None else max(self.cpu_max, cpu)
        self.mem_max = mem if self.mem_max is None else max(self.mem_max, mem)


def _to_mib(text: str) -> float:
    units = {"KiB": 1 / 1024, "MiB": 1.0, "GiB": 1024.0, "B": 1 / (1024 * 1024)}
    for unit, factor in units.items():
        if text.endswith(unit):
            return float(text[: -len(unit)]) * factor
    return float(text)


async def _poll_pool(client: httpx.AsyncClient, runtime_url: str, stop: asyncio.Event) -> int:
    peak = 0
    while not stop.is_set():
        try:
            info = (await client.get(f"{runtime_url}/info")).json()
            peak = max(peak, int(info.get("pool", {}).get("admitted", 0)))
        except (httpx.HTTPError, ValueError):
            pass
        await asyncio.sleep(0.25)
    return peak


async def run_level(
    *,
    url: str,
    runtime_url: str | None,
    audio: bytes,
    params: dict[str, str],
    concurrency: int,
    repetitions: int,
    clip_seconds: float,
    docker_container: str | None,
    timeout_seconds: float,
) -> LevelResult:
    sampler = DockerSampler(docker_container)
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        stop = asyncio.Event()
        pool_task = (
            asyncio.create_task(_poll_pool(client, runtime_url, stop)) if runtime_url else None
        )

        async def worker() -> list[RequestSample]:
            samples = []
            for _ in range(repetitions):
                samples.append(await _one_request(client, url, audio, params))
                await asyncio.to_thread(sampler.sample_once)
            return samples

        # Two serial warm probes, excluded from the sample.
        for _ in range(2):
            await _one_request(client, url, audio, params)

        started = time.perf_counter()
        batches = await asyncio.gather(*(worker() for _ in range(concurrency)))
        wall = time.perf_counter() - started
        stop.set()
        max_admitted = await pool_task if pool_task else None

    samples = [sample for batch in batches for sample in batch]
    succeeded = [sample for sample in samples if sample.ok]
    latencies = sorted(sample.client_ms for sample in succeeded)
    inference = [
        sample.stages_ms["inference"] for sample in succeeded if "inference" in sample.stages_ms
    ]
    return LevelResult(
        concurrency=concurrency,
        requests=len(samples),
        succeeded=len(succeeded),
        overloaded=sum(1 for sample in samples if sample.status == 503),
        other_errors=sum(1 for sample in samples if not sample.ok and sample.status != 503),
        wall_seconds=round(wall, 2),
        p50_ms=round(nearest_rank(latencies, 0.50), 1) if latencies else None,
        p95_ms=round(nearest_rank(latencies, 0.95), 1) if latencies else None,
        throughput_rps=round(len(succeeded) / wall, 3) if wall > 0 else 0.0,
        mean_rtf=(
            round(sum(inference) / len(inference) / 1000.0 / clip_seconds, 4) if inference else None
        ),
        max_pool_admitted=max_admitted,
        docker_cpu_percent_max=sampler.cpu_max,
        docker_memory_mib_max=sampler.mem_max,
    )


async def measure_overhead(
    *,
    gateway_url: str,
    runtime_url: str,
    api_key: str,
    public_model: str,
    artifact: str,
    audio: bytes,
    repetitions: int,
    timeout_seconds: float,
    language: str | None = None,
) -> OverheadResult:
    """ADR-0002 check: same clip, same repetitions, both paths, medians.

    ``language`` is sent on BOTH paths when given. Without it the ladder
    measured auto-detection while the quality pass measured an explicit
    declaration - and the declared language is a first-order cost variable
    on our own hardware, so the two halves of one session described
    different systems.
    """
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        runtime_body: dict[str, str] = {"model": artifact}
        gateway_params: dict[str, str] = {"model": public_model}
        if language is not None:
            # Both paths, or the comparison is between two different systems.
            runtime_body["language"] = language
            gateway_params["language"] = language
        direct_params = {"params": json.dumps(runtime_body)}
        headers = {"Authorization": f"Bearer {api_key}"}
        direct_url = f"{runtime_url}/v1/transcribe"
        via_url = f"{gateway_url}/v1/audio/transcriptions"
        # Warm both paths, excluded.
        await _one_request(client, direct_url, audio, direct_params)
        await _one_request(client, via_url, audio, gateway_params, headers)

        direct: list[RequestSample] = []
        via: list[RequestSample] = []
        for _ in range(repetitions):
            direct.append(await _one_request(client, direct_url, audio, direct_params))
            via.append(await _one_request(client, via_url, audio, gateway_params, headers))

    direct_lat = sorted(sample.client_ms for sample in direct if sample.ok)
    via_lat = sorted(sample.client_ms for sample in via if sample.ok)
    inference = sorted(
        sample.stages_ms["inference"] for sample in direct if "inference" in sample.stages_ms
    )
    direct_p50 = nearest_rank(direct_lat, 0.50)
    via_p50 = nearest_rank(via_lat, 0.50)
    inference_p50 = nearest_rank(inference, 0.50)
    overhead = via_p50 - direct_p50
    return OverheadResult(
        direct_p50_ms=round(direct_p50, 1),
        via_gateway_p50_ms=round(via_p50, 1),
        gateway_overhead_ms=round(overhead, 1),
        inference_p50_ms=round(inference_p50, 1),
        overhead_fraction_of_inference=round(overhead / inference_p50, 4),
    )
