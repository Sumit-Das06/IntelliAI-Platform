"""M32 — prosody-pair analysis: does punctuation change the rendered speech?

For each prosody pair in the probe set (same words, with/without the mark) this
script compares the two WAVs an engine produced: duration, trailing-silence-
stripped duration, mean F0 and the F0 slope over the final 40% of voiced frames
(a rising terminal contour is the acoustic signature of a question).

F0 comes from a plain autocorrelation estimator (25 ms frames, 10 ms hop, 60-400
Hz search, voiced = energy above threshold). Signal-level facts only — whether a
contour difference is *audible and natural* stays a human-listening question and
is labeled that way in the report.

Runs in the kokoro research venv (numpy available):
    python prosody_analyze.py --probes probe-texts-v1.json --audio-dir <dir> --out <json>
"""

from __future__ import annotations

import argparse
import json
import wave
from pathlib import Path

import numpy as np


def read_wav(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as fh:
        rate = fh.getframerate()
        pcm = np.frombuffer(fh.readframes(fh.getnframes()), dtype="<i2")
    return pcm.astype(np.float32) / 32768.0, rate


def strip_trailing_silence(audio: np.ndarray, rate: int, threshold: float = 0.01) -> np.ndarray:
    frame = max(1, rate // 100)
    total_frames = len(audio) // frame
    last_voiced = 0
    for index in range(total_frames):
        chunk = audio[index * frame : (index + 1) * frame]
        if np.sqrt(np.mean(chunk**2)) > threshold:
            last_voiced = index
    return audio[: (last_voiced + 1) * frame]


def f0_track(audio: np.ndarray, rate: int) -> list[float]:
    frame_length = int(rate * 0.025)
    hop = int(rate * 0.010)
    low, high = 60.0, 400.0
    lag_min = int(rate / high)
    lag_max = int(rate / low)
    track: list[float] = []
    for start in range(0, len(audio) - frame_length, hop):
        frame = audio[start : start + frame_length]
        if np.sqrt(np.mean(frame**2)) < 0.02:
            continue
        frame = frame - np.mean(frame)
        correlation = np.correlate(frame, frame, mode="full")[frame_length - 1 :]
        if correlation[0] <= 0:
            continue
        window = correlation[lag_min : min(lag_max, len(correlation) - 1)]
        if len(window) == 0:
            continue
        lag = int(np.argmax(window)) + lag_min
        if correlation[lag] / correlation[0] < 0.3:
            continue
        track.append(rate / lag)
    return track


def describe(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    audio, rate = read_wav(path)
    voiced = strip_trailing_silence(audio, rate)
    track = f0_track(voiced, rate)
    tail = track[int(len(track) * 0.6) :] if len(track) >= 5 else []
    slope = None
    if len(tail) >= 3:
        xs = np.arange(len(tail), dtype=np.float32)
        slope = float(np.polyfit(xs, np.asarray(tail, dtype=np.float32), 1)[0])
    return {
        "duration_s": round(len(audio) / rate, 3),
        "voiced_duration_s": round(len(voiced) / rate, 3),
        "f0_mean_hz": round(float(np.mean(track)), 1) if track else None,
        "f0_tail_slope_hz_per_frame": round(slope, 3) if slope is not None else None,
        "voiced_frames": len(track),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--probes", required=True)
    parser.add_argument("--audio-dir", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    probes = json.loads(Path(args.probes).read_text(encoding="utf-8"))["cases"]
    pairs: dict[str, dict[str, dict[str, object]]] = {}
    audio_dir = Path(args.audio_dir).expanduser()
    for case in probes:
        pair = case.get("pair")
        if not pair:
            continue
        described = describe(audio_dir / f"{case['id']}.wav")
        if described is None:
            continue
        pairs.setdefault(pair, {})[case["variant"]] = described

    rows = []
    for pair, variants in sorted(pairs.items()):
        with_mark = variants.get("with_mark")
        without_mark = variants.get("without_mark")
        row: dict[str, object] = {
            "pair": pair,
            "with_mark": with_mark,
            "without_mark": without_mark,
        }
        keys = ("duration_s", "voiced_duration_s", "f0_mean_hz", "f0_tail_slope_hz_per_frame")
        if with_mark and without_mark:
            for key in keys:
                left, right = with_mark.get(key), without_mark.get(key)
                if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                    row[f"delta_{key}"] = round(float(left) - float(right), 3)
        rows.append(row)

    report = {
        "experiment": "32-tts-model-selection",
        "instrument": "prosody_analyze.py",
        "method": (
            "autocorrelation F0 (25ms/10ms, 60-400Hz, voicing by energy); tail slope over "
            "the final 40% of voiced frames; signal-level facts only — naturalness remains "
            "a human-listening question"
        ),
        "audio_dir": str(audio_dir),
        "pairs": rows,
    }
    Path(args.out).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"prosody: analyzed {len(rows)} pairs -> {args.out}")


if __name__ == "__main__":
    main()
