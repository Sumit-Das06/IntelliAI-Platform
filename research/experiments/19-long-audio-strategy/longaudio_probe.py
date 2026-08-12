"""Long-audio strategy probes: larger context vs chunking, MEASURED.

NOT ledger evidence. Sandbox probes against a hand-spawned pinned
llama-server (the engine's exact request shape: greedy, wav transport)
to answer the Milestone 19 research questions:

  A. At ctx 8192/16384, does long Hindi audio transcribe COMPLETELY,
     at what CER, at what RSS/latency? (ctx 4096 rows are the control
     that reproduces the known truncation.)
  B. Does fixed-window chunking with overlap-dedup merging match the
     large-context transcript quality while keeping RSS flat?

References ARE valid here, unlike the M17 completeness probe: the long
inputs are concatenations of FROZEN-EVAL clips, so the reference is the
concatenation of their references, scored with the evaluation plane's
own ruler (cer_unicode / unicode_generic@v2). These numbers are labeled
"concatenated-clip probe" — read beside the frozen benchmark, never
entered in the results ledger.
"""

from __future__ import annotations

import argparse
import base64
import datetime
import json
import subprocess
import threading
import time
import urllib.request
import wave
from pathlib import Path
from typing import Any

from intelliai_evaluation.accuracy import score
from intelliai_evaluation.dataset import load_dataset
from intelliai_evaluation.normalization import profile_for

ASR_MARKER = "<asr_text>"
PROMPT = "Transcribe the audio."


# ── Long-input construction (deterministic, references preserved) ───────


def build_concat(manifest: Path, data_root: Path, seconds: int, work: Path) -> tuple[Path, str]:
    """First natural clips of the frozen manifest until >= `seconds`.

    Returns (wav path, concatenated reference). Cached by duration.
    """
    wav_path = work / f"concat-{seconds}s.wav"
    ref_path = work / f"concat-{seconds}s.ref.txt"
    if wav_path.exists() and ref_path.exists():
        return wav_path, ref_path.read_text(encoding="utf-8")
    dataset = load_dataset(manifest)
    natural = [c for c in dataset.clips if c.synthetic is None]
    total, chosen = 0.0, []
    for clip in natural:
        chosen.append(clip)
        total += clip.duration_seconds
        if total >= seconds:
            break
    listing = work / f"concat-{seconds}s.txt"
    listing.write_text(
        "".join(f"file '{(data_root / c.filename).resolve().as_posix()}'\n" for c in chosen),
        encoding="utf-8",
    )
    subprocess.run(  # noqa: S603 — ffmpeg from PATH, probe tooling
        [  # noqa: S607
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(listing),
            "-t",
            str(seconds),
            "-ar",
            "16000",
            "-ac",
            "1",
            "-sample_fmt",
            "s16",
            str(wav_path),
        ],
        check=True,
        timeout=300,
    )
    # The final clip may be cut by -t; its reference stays included — the
    # induced error is identical across every strategy, so comparisons
    # between strategies remain fair (absolute CER carries a small,
    # constant, documented pessimism).
    reference = " ".join(c.reference_text for c in chosen)
    ref_path.write_text(reference, encoding="utf-8")
    return wav_path, reference


# ── The engine's exact request shape ─────────────────────────────────────


def transcribe_wav(base_url: str, wav_bytes: bytes, max_tokens: int, timeout: float) -> str:
    payload = {
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_audio",
                        "input_audio": {
                            "data": base64.b64encode(wav_bytes).decode("ascii"),
                            "format": "wav",
                        },
                    },
                    {"type": "text", "text": PROMPT},
                ],
            }
        ],
        "temperature": 0.0,
        "max_tokens": max_tokens,
    }
    request = urllib.request.Request(  # noqa: S310 — loopback probe
        f"{base_url}/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        body = json.loads(response.read().decode("utf-8"))
    content = str(body["choices"][0]["message"]["content"])
    if ASR_MARKER in content:
        content = content.partition(ASR_MARKER)[2]
    return content.strip()


def wav_window(source: Path, start: float, length: float, work: Path, tag: str) -> bytes:
    out = work / f"win-{tag}.wav"
    subprocess.run(  # noqa: S603
        [  # noqa: S607
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-ss",
            str(start),
            "-t",
            str(length),
            "-i",
            str(source),
            "-ar",
            "16000",
            "-ac",
            "1",
            "-sample_fmt",
            "s16",
            str(out),
        ],
        check=True,
        timeout=120,
    )
    return out.read_bytes()


# ── Overlap-aware merge (the chunking design under test) ─────────────────


def merge_overlap(previous: str, nxt: str, profile: Any, window: int = 14) -> str:
    """Append `nxt`, dropping its words that re-say the overlap tail.

    Longest suffix(previous)/prefix(next) match on NORMALIZED words —
    exact-match on the ruler's own normalization, so 'match' means what
    the evaluation plane means by it.
    """
    prev_words = previous.split()
    next_words = nxt.split()
    prev_norm = [" ".join(profile.words(w)) for w in prev_words[-window:]]
    next_norm = [" ".join(profile.words(w)) for w in next_words[: window * 2]]
    best = 0
    for k in range(min(len(prev_norm), len(next_norm)), 0, -1):
        if prev_norm[-k:] == next_norm[:k]:
            best = k
            break
    return " ".join(prev_words + next_words[best:])


# ── RSS sampling of the server under test ────────────────────────────────


class RssSampler:
    def __init__(self) -> None:
        self.peak_mib = 0.0
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.wait(0.4):
            out = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq llama-server.exe", "/FO", "CSV", "/NH"],  # noqa: S607
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            ).stdout
            for line in out.splitlines():
                parts = [p.strip('"') for p in line.split('","')]
                if len(parts) >= 5 and parts[0].lower() == "llama-server.exe":
                    kib = float(parts[4].replace(" K", "").replace(",", "").replace(".", ""))
                    self.peak_mib = max(self.peak_mib, kib / 1024)

    def stop(self) -> float:
        self._stop.set()
        self._thread.join(timeout=3)
        return round(self.peak_mib, 1)


def tail_repetition(text: str, window: int = 40) -> float:
    if len(text) < window * 3:
        return 0.0
    tail = text[-window * 10 :]
    shingle = tail[-window:]
    return round((tail.count(shingle) - 1) * window / max(len(tail), 1), 3)


# ── Probe modes ──────────────────────────────────────────────────────────


def run_direct(
    base_url: str, wav_path: Path, reference: str, profile: Any, max_tokens: int
) -> dict[str, Any]:
    sampler = RssSampler()
    started = time.perf_counter()
    failure = None
    text = ""
    try:
        text = transcribe_wav(base_url, wav_path.read_bytes(), max_tokens, timeout=1800)
    except Exception as exc:
        failure = f"{type(exc).__name__}: {exc}"[:200]
    wall = round(time.perf_counter() - started, 1)
    return _row(text, reference, profile, wall, sampler.stop(), failure)


def run_chunked(
    base_url: str,
    wav_path: Path,
    reference: str,
    profile: Any,
    work: Path,
    *,
    chunk_seconds: float,
    overlap_seconds: float,
    max_tokens: int,
) -> dict[str, Any]:
    with wave.open(str(wav_path)) as reader:
        duration = reader.getnframes() / reader.getframerate()
    sampler = RssSampler()
    started = time.perf_counter()
    merged = ""
    chunks = 0
    failure = None
    step = chunk_seconds - overlap_seconds
    seams: list[str] = []
    try:
        start = 0.0
        while start < duration:
            tag = f"{int(start)}"
            piece = wav_window(wav_path, start, chunk_seconds, work, tag)
            text = transcribe_wav(base_url, piece, max_tokens, timeout=900)
            chunks += 1
            if merged:
                seams.append(f"…{merged[-60:]} ⇢ {text[:60]}…")
                merged = merge_overlap(merged, text, profile)
            else:
                merged = text
            start += step
    except Exception as exc:
        failure = f"{type(exc).__name__}: {exc}"[:200]
    wall = round(time.perf_counter() - started, 1)
    row = _row(merged, reference, profile, wall, sampler.stop(), failure)
    row["chunks"] = chunks
    row["chunk_seconds"] = chunk_seconds
    row["overlap_seconds"] = overlap_seconds
    row["seams"] = seams
    return row


def _row(
    text: str, reference: str, profile: Any, wall: float, peak_rss: float, failure: str | None
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "failure": failure,
        "wall_seconds": wall,
        "peak_rss_mib": peak_rss,
        "output_chars": len(text),
        "tail_repetition": tail_repetition(text),
        "text_tail": text[-120:],
    }
    if failure is None and text:
        result = score(reference, text, profile)
        row["cer_unicode"] = round(result.cer, 4)
        row["wer_unicode"] = round(result.wer, 4)
        ref_chars = len(profile.characters(reference))
        hyp_chars = len(profile.characters(text))
        row["completeness_chars"] = round(hyp_chars / ref_chars, 3) if ref_chars else None
    return row


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8090")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, default=Path("ml/datasets/data"))
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--mode", choices=["direct", "chunked"], required=True)
    parser.add_argument("--durations", default="120,180,300,600")
    parser.add_argument("--label", required=True, help="e.g. ctx8192 | chunk100x5")
    parser.add_argument("--max-tokens", type=int, default=6000)
    parser.add_argument("--chunk-seconds", type=float, default=100.0)
    parser.add_argument("--overlap-seconds", type=float, default=5.0)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    args.work.mkdir(parents=True, exist_ok=True)
    profile = profile_for("hi")
    rows: dict[str, Any] = {}
    for seconds in (int(s) for s in args.durations.split(",")):
        wav_path, reference = build_concat(args.manifest, args.data_root, seconds, args.work)
        if args.mode == "direct":
            rows[f"{seconds}s"] = run_direct(
                args.base_url, wav_path, reference, profile, args.max_tokens
            )
        else:
            rows[f"{seconds}s"] = run_chunked(
                args.base_url,
                wav_path,
                reference,
                profile,
                args.work,
                chunk_seconds=args.chunk_seconds,
                overlap_seconds=args.overlap_seconds,
                max_tokens=args.max_tokens,
            )
        summary = {k: v for k, v in rows[f"{seconds}s"].items() if k != "seams"}
        print(f"[{args.label}] {seconds}s -> {json.dumps(summary, ensure_ascii=False)[:300]}")

    payload = {
        "probe": "19-long-audio-strategy",
        "NOT_LEDGER_EVIDENCE": (
            "concatenated-clip sandbox probe; read beside the frozen benchmark, never entered in it"
        ),
        "label": args.label,
        "mode": args.mode,
        "run_at": datetime.datetime.now(tz=datetime.UTC).isoformat(),
        "rows": rows,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    existing = {}
    if args.out.exists():
        existing = json.loads(args.out.read_text(encoding="utf-8"))
    existing[args.label] = payload
    args.out.write_text(json.dumps(existing, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"written: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
