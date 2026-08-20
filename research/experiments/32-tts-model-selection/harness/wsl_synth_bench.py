"""M32 research synthesis bench — candidate engines in scratch venvs (research only).

Runs INSIDE a disposable WSL venv that carries the candidate's own dependencies
(including, for the Hindi spike, the GPL espeak chain — research use only; the
production image stays GPL-free by construction and this script never runs there).

One engine per invocation; identical probe texts across engines; WAVs land in a
NON-repo audio dir (audio never enters git). Per-probe wall time, audio seconds,
RTF, and time-to-first-audio (for engines that yield incrementally) are recorded,
plus process RSS before/after load and peak (VmHWM), package versions, and the
resolved Hugging Face revision where the engine downloads from the hub.

Usage (inside the engine's venv):
    python wsl_synth_bench.py --engine kokoro-hi --probes probe-texts-v1.json \
        --audio-dir ~/m32/audio/kokoro-hi --out kokoro-hi-bench.json \
        --languages hi,mixed,mixed-roman --voice hf_alpha
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import wave
from pathlib import Path


def _rss_mib() -> float:
    with open("/proc/self/status", encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) / 1024.0
    return 0.0


def _peak_rss_mib() -> float:
    with open("/proc/self/status", encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("VmHWM:"):
                return int(line.split()[1]) / 1024.0
    return 0.0


def _write_wav(path: Path, pcm: bytes, sample_rate: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as fh:
        fh.setnchannels(1)
        fh.setsampwidth(2)
        fh.setframerate(sample_rate)
        fh.writeframes(pcm)


def _to_pcm16(audio: object) -> bytes:  # numpy array or torch tensor -> int16 LE bytes
    import numpy as np

    arr = audio
    if hasattr(arr, "detach"):  # torch tensor
        arr = arr.detach().cpu().numpy()
    arr = np.asarray(arr, dtype=np.float32).reshape(-1)
    arr = np.clip(arr, -1.0, 1.0)
    return (arr * 32767.0).astype("<i2").tobytes()


class KokoroAdapter:
    """Stock upstream pipeline (KPipeline) — the research twin of the engine.

    lang 'a' = American English (misaki native G2P, espeak only as OOV fallback);
    lang 'h' = Hindi (espeak-ng G2P — the GPL chain, research venv only). The
    production runtime bypasses KPipeline and bans espeak; this adapter exists to
    measure what the upstream path CAN do before any compliant re-plumbing.
    """

    def __init__(self, lang_code: str, voice: str) -> None:
        self.lang_code = lang_code
        self.voice = voice
        self.sample_rate = 24_000
        self.pipeline = None
        self.hub_revision = "unknown"

    def load(self) -> None:
        from kokoro import KModel, KPipeline

        try:
            from huggingface_hub import model_info

            self.hub_revision = str(model_info("hexgrad/Kokoro-82M").sha)
        except Exception as exc:
            self.hub_revision = f"unresolved ({exc.__class__.__name__})"
        model = KModel().eval()
        self.pipeline = KPipeline(lang_code=self.lang_code, model=model)

    def synthesize(self, text: str) -> tuple[bytes, float | None]:
        """Returns (pcm16, ttfa_seconds). TTFA = first yielded chunk's arrival."""
        if self.pipeline is None:
            raise RuntimeError("load() must run first")
        started = time.perf_counter()
        ttfa: float | None = None
        pieces: list[bytes] = []
        for result in self.pipeline(text, voice=self.voice):
            audio = getattr(result, "audio", None)
            if audio is None:
                continue
            if ttfa is None:
                ttfa = time.perf_counter() - started
            pieces.append(_to_pcm16(audio))
        return b"".join(pieces), ttfa

    def identity(self) -> dict[str, object]:
        import kokoro

        return {
            "engine": "kokoro-82m (upstream KPipeline)",
            "lang_code": self.lang_code,
            "voice": self.voice,
            "kokoro_version": getattr(kokoro, "__version__", "unknown"),
            "hub_repo": "hexgrad/Kokoro-82M",
            "hub_revision": self.hub_revision,
            "gpl_espeak_chain_in_process": any(
                name in sys.modules for name in ("espeakng_loader", "phonemizer")
            ),
        }


class KittenAdapter:
    """KittenTTS nano. License fact recorded per run: the pip package phonemizes
    ENGLISH through the GPL espeak chain (phonemizer EspeakBackend) in-process,
    unconditionally — Apache weights, but no espeak-free G2P path exists."""

    def __init__(self, voice: str) -> None:
        self.voice = voice
        self.sample_rate = 24_000
        self.model = None
        self.repo = "KittenML/kitten-tts-nano-0.2"
        self.hub_revision = "unknown"
        self.resolved_files: tuple[str, str] | None = None

    def load(self) -> None:
        from huggingface_hub import hf_hub_download, list_repo_files, model_info
        from kittentts import KittenTTS

        try:
            self.hub_revision = str(model_info(self.repo).sha)
            files = list_repo_files(self.repo)
            onnx_name = next(name for name in files if name.endswith(".onnx"))
            voices_name = next(name for name in files if name.endswith(".npz"))
            model_path = hf_hub_download(self.repo, onnx_name)
            voices_path = hf_hub_download(self.repo, voices_name)
            self.resolved_files = (onnx_name, voices_name)
            self.model = KittenTTS(model_path, voices_path)
        except Exception:
            self.repo = "KittenML/kitten-tts-nano-0.1 (pip default fallback)"
            self.model = KittenTTS()

    def synthesize(self, text: str) -> tuple[bytes, float | None]:
        if self.model is None:
            raise RuntimeError("load() must run first")
        audio = self.model.generate(text, voice=self.voice)
        return _to_pcm16(audio), None  # single-shot: no incremental yield

    def identity(self) -> dict[str, object]:
        return {
            "engine": "kitten-tts-nano",
            "voice": self.voice,
            "hub_repo": self.repo,
            "hub_revision": self.hub_revision,
            "resolved_files": self.resolved_files,
            "license_note": "Apache-2.0 weights; English G2P runs the GPL espeak chain in-process",
            "gpl_espeak_chain_in_process": any(
                name in sys.modules for name in ("espeakng_loader", "phonemizer")
            ),
        }


class SupertonicAdapter:
    """Supertonic 3 via the vendor's `supertonic` PyPI package (defaults to the
    supertonic-3 assets; `lang` selects the language pipeline).

    License note recorded with every run: model weights are OpenRAIL-M (use-based
    restrictions; NOT a permissive license) — REVIEW REQUIRED before any adoption.
    """

    def __init__(self, language: str, voice: str) -> None:
        self.language = language
        self.voice = voice
        self.sample_rate = 44_100  # per repo docs; overwritten with the actual rate
        self.tts = None
        self.style = None

    def load(self) -> None:
        from supertonic import TTS

        self.tts = TTS(model="supertonic-3", auto_download=True)
        self.style = self.tts.get_voice_style(voice_name=self.voice)
        rate = getattr(self.tts, "sample_rate", None)
        if isinstance(rate, int) and rate > 0:
            self.sample_rate = rate

    def synthesize(self, text: str) -> tuple[bytes, float | None]:
        if self.tts is None:
            raise RuntimeError("load() must run first")
        wav, _duration = self.tts.synthesize(text, voice_style=self.style, lang=self.language)
        return _to_pcm16(wav), None

    def identity(self) -> dict[str, object]:
        import supertonic

        return {
            "engine": "supertonic-3 (pypi)",
            "package_version": getattr(supertonic, "__version__", "unknown"),
            "language": self.language,
            "voice": self.voice,
            "sample_rate_hz": self.sample_rate,
            "license_note": "model weights OpenRAIL-M - REVIEW REQUIRED, not permissive",
        }


def build_adapter(args: argparse.Namespace) -> object:
    if args.engine == "kokoro-en":
        return KokoroAdapter(lang_code="a", voice=args.voice or "af_heart")
    if args.engine == "kokoro-hi":
        return KokoroAdapter(lang_code="h", voice=args.voice or "hf_alpha")
    if args.engine == "kitten":
        return KittenAdapter(voice=args.voice or "expr-voice-2-f")
    if args.engine in ("supertonic-en", "supertonic-hi"):
        lang = "en" if args.engine.endswith("en") else "hi"
        return SupertonicAdapter(lang, args.voice or "M1")
    raise SystemExit(f"unknown engine {args.engine!r}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", required=True)
    parser.add_argument("--probes", required=True)
    parser.add_argument("--audio-dir", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--languages", default="")
    parser.add_argument("--voice", default=None)
    parser.add_argument("--supertonic-dir", default="~/m32/supertonic")
    parser.add_argument("--repetitions", type=int, default=1)
    args = parser.parse_args()

    probes = json.loads(Path(args.probes).read_text(encoding="utf-8"))["cases"]
    wanted = {piece.strip() for piece in args.languages.split(",") if piece.strip()}
    if wanted:
        probes = [case for case in probes if case["language"] in wanted]

    adapter = build_adapter(args)
    rss_before = _rss_mib()
    load_started = time.perf_counter()
    adapter.load()
    load_seconds = time.perf_counter() - load_started
    rss_after_load = _rss_mib()

    audio_dir = Path(args.audio_dir).expanduser()
    rows: list[dict[str, object]] = []
    failures: list[dict[str, object]] = []
    warm_text = "नमस्ते।" if args.engine == "kokoro-hi" else "Warm up run."
    adapter.synthesize(warm_text)

    for case in probes:
        text = case["text"]
        best: dict[str, object] | None = None
        for _ in range(max(1, args.repetitions)):
            started = time.perf_counter()
            try:
                pcm, ttfa = adapter.synthesize(text)
            except Exception as exc:
                failures.append({"id": case["id"], "error": f"{exc.__class__.__name__}: {exc}"})
                pcm, ttfa = b"", None
                break
            wall = time.perf_counter() - started
            seconds = (len(pcm) // 2) / adapter.sample_rate if pcm else 0.0
            row = {
                "id": case["id"],
                "language": case["language"],
                "category": case.get("category"),
                "chars": len(text),
                "wall_ms": round(wall * 1000.0, 1),
                "ttfa_ms": round(ttfa * 1000.0, 1) if ttfa is not None else None,
                "audio_seconds": round(seconds, 3),
                "rtf": round(wall / seconds, 4) if seconds > 0 else None,
            }
            if best is None or row["wall_ms"] < best["wall_ms"]:  # type: ignore[operator]
                best = row
        if best is None:
            continue
        if pcm:
            _write_wav(audio_dir / f"{case['id']}.wav", pcm, adapter.sample_rate)
        rows.append(best)

    ok_rows = [row for row in rows if row["audio_seconds"] and row["rtf"] is not None]
    rtfs = sorted(float(row["rtf"]) for row in ok_rows)  # type: ignore[arg-type]
    report = {
        "experiment": "32-tts-model-selection",
        "instrument": "wsl_synth_bench.py",
        "engine": args.engine,
        "identity": adapter.identity(),
        "sample_rate_hz": adapter.sample_rate,
        "probes_file": Path(args.probes).name,
        "repetitions": args.repetitions,
        "load_seconds": round(load_seconds, 2),
        "rss_before_load_mib": round(rss_before, 1),
        "rss_after_load_mib": round(rss_after_load, 1),
        "rss_peak_mib": round(_peak_rss_mib(), 1),
        "probe_count": len(rows),
        "failure_count": len(failures),
        "failures": failures,
        "rtf_median": rtfs[len(rtfs) // 2] if rtfs else None,
        "rtf_p95": rtfs[min(len(rtfs) - 1, int(0.95 * len(rtfs)))] if rtfs else None,
        "rows": rows,
    }
    Path(args.out).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(
        f"{args.engine}: {len(rows)} probes, {len(failures)} failures, "
        f"median RTF {report['rtf_median']}, peak RSS {report['rss_peak_mib']} MiB"
    )


if __name__ == "__main__":
    main()
