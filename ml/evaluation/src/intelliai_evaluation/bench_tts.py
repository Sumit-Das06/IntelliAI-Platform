"""TTS production benchmark — the binary binding's ruler, beside bench.py.

Same deterministic methodology as the transcription bench (client-side
wall clock, nearest-rank percentiles, saturation counted never hidden,
docker stats sampling), adapted to the binary binding (ADR-0020): JSON
text in, WAV body out, the runtime envelope riding X-Runtime-Envelope.

Engine-agnostic by construction: the bench speaks the PUBLIC binding —
swapping the engine behind the runtime changes the numbers, never the
methodology. The same ruler measures every successor.

TTFB note: v1 serves unstreamed responses, so time-to-first-byte equals
full response latency — the honest (conservative) reading of the PRD
target. Streaming, if it ever lands (M8), can only improve this number.
"""

from __future__ import annotations

import asyncio
import json
import time

import httpx
from pydantic import BaseModel, ConfigDict

from intelliai_evaluation.bench import DockerSampler, LevelResult, OverheadResult, nearest_rank

HEADER_RUNTIME_ENVELOPE = "X-Runtime-Envelope"

# The pinned benchmark sentence: fixed IN CODE so every run of this tool,
# forever, measures the same input (the bench analogue of a pinned clip).
BENCH_TEXT = (
    "IntelliAI turns text into natural speech. This fixed benchmark "
    "sentence measures synthesis latency and real time factor."
)


class TtsSample(BaseModel):
    model_config = ConfigDict(frozen=True)

    ok: bool
    status: int
    client_ms: float
    synthesis_ms: float | None = None
    audio_seconds: float | None = None


def sample_from_response(status: int, envelope_header: str | None, client_ms: float) -> TtsSample:
    """Pure parser: HTTP facts -> one sample (testable without a socket)."""
    if status != 200:
        return TtsSample(ok=False, status=status, client_ms=client_ms)
    synthesis_ms: float | None = None
    audio_seconds: float | None = None
    if envelope_header is not None:
        try:
            envelope = json.loads(envelope_header)
            stages = envelope.get("timing", {}).get("stages", {})
            raw = stages.get("synthesis")
            synthesis_ms = float(raw) if raw is not None else None
            audio_seconds = float(envelope["output"]["duration_seconds"])
        except (ValueError, KeyError, TypeError):
            synthesis_ms = None
            audio_seconds = None
    return TtsSample(
        ok=True,
        status=200,
        client_ms=client_ms,
        synthesis_ms=synthesis_ms,
        audio_seconds=audio_seconds,
    )


async def _one_synthesis(
    client: httpx.AsyncClient,
    url: str,
    body: dict[str, object],
    headers: dict[str, str] | None = None,
) -> TtsSample:
    started = time.perf_counter()
    try:
        response = await client.post(url, json=body, headers=headers or {})
    except httpx.HTTPError:
        return TtsSample(ok=False, status=0, client_ms=(time.perf_counter() - started) * 1000)
    client_ms = (time.perf_counter() - started) * 1000
    return sample_from_response(
        response.status_code, response.headers.get(HEADER_RUNTIME_ENVELOPE), client_ms
    )


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


async def run_tts_level(
    *,
    url: str,
    runtime_url: str | None,
    body: dict[str, object],
    concurrency: int,
    repetitions: int,
    docker_container: str | None,
    timeout_seconds: float,
) -> LevelResult:
    sampler = DockerSampler(docker_container)
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        stop = asyncio.Event()
        pool_task = (
            asyncio.create_task(_poll_pool(client, runtime_url, stop)) if runtime_url else None
        )

        async def worker() -> list[TtsSample]:
            samples = []
            for _ in range(repetitions):
                samples.append(await _one_synthesis(client, url, body))
                await asyncio.to_thread(sampler.sample_once)
            return samples

        # Two serial warm probes, excluded from the sample.
        for _ in range(2):
            await _one_synthesis(client, url, body)

        started = time.perf_counter()
        batches = await asyncio.gather(*(worker() for _ in range(concurrency)))
        wall = time.perf_counter() - started
        stop.set()
        max_admitted = await pool_task if pool_task else None

    samples = [sample for batch in batches for sample in batch]
    succeeded = [sample for sample in samples if sample.ok]
    latencies = sorted(sample.client_ms for sample in succeeded)
    rtfs = [
        sample.synthesis_ms / 1000.0 / sample.audio_seconds
        for sample in succeeded
        if sample.synthesis_ms is not None and sample.audio_seconds
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
        mean_rtf=round(sum(rtfs) / len(rtfs), 4) if rtfs else None,
        max_pool_admitted=max_admitted,
        docker_cpu_percent_max=sampler.cpu_max,
        docker_memory_mib_max=sampler.mem_max,
    )


async def measure_tts_overhead(
    *,
    gateway_url: str,
    runtime_url: str,
    api_key: str,
    public_model: str,
    artifact: str,
    voice: str,
    text: str,
    repetitions: int,
    timeout_seconds: float,
) -> OverheadResult:
    """ADR-0002 check, synthesis edition: same text, both paths, medians."""
    direct_body: dict[str, object] = {"text": text, "voice": voice, "model": artifact}
    gateway_body: dict[str, object] = {"model": public_model, "input": text, "voice": voice}
    headers = {"Authorization": f"Bearer {api_key}"}
    direct_url = f"{runtime_url}/v1/synthesize"
    via_url = f"{gateway_url}/v1/audio/speech"
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        # Warm both paths, excluded.
        await _one_synthesis(client, direct_url, direct_body)
        await _one_synthesis(client, via_url, gateway_body, headers)

        direct: list[TtsSample] = []
        via: list[TtsSample] = []
        for _ in range(repetitions):
            direct.append(await _one_synthesis(client, direct_url, direct_body))
            via.append(await _one_synthesis(client, via_url, gateway_body, headers))

    direct_lat = sorted(sample.client_ms for sample in direct if sample.ok)
    via_lat = sorted(sample.client_ms for sample in via if sample.ok)
    synthesis = sorted(
        sample.synthesis_ms for sample in direct if sample.ok and sample.synthesis_ms is not None
    )
    direct_p50 = nearest_rank(direct_lat, 0.50)
    via_p50 = nearest_rank(via_lat, 0.50)
    synthesis_p50 = nearest_rank(synthesis, 0.50)
    overhead = via_p50 - direct_p50
    return OverheadResult(
        direct_p50_ms=round(direct_p50, 1),
        via_gateway_p50_ms=round(via_p50, 1),
        gateway_overhead_ms=round(overhead, 1),
        inference_p50_ms=round(synthesis_p50, 1),
        overhead_fraction_of_inference=round(overhead / synthesis_p50, 4),
    )


class TtsBenchReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    text: str
    characters: int
    audio_seconds: float | None
    repetitions_per_worker: int
    hardware: str
    notes: str = ""
    levels: list[LevelResult]
    overhead: OverheadResult | None = None
    prd_ttfb_target_ms: float
    prd_ttfb_actual_ms: float | None
    prd_verdict: str
