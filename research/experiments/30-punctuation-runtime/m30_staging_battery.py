"""M30 — staging battery through the production-shaped stack (Caddy edge).

Real HTTPS requests against the local production-shaped deployment with
the punctuation stage ENABLED (the only committed deployment that enables
it). Every drill records PASS/FAIL into staging-battery.json. Audio is
approved public data (IndicVoices valid split, JFK probe) and synthetic
silence/noise — never customer audio, never committed.

Usage (repo root, stack up):
  python .../m30_staging_battery.py build-fixtures
  python .../m30_staging_battery.py run
  python .../m30_staging_battery.py drill-disabled   (after the off-overlay restart)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SCRATCH = Path(os.environ.get("M30_SCRATCH", str(HERE / "_fixtures")))
BASE = "https://localhost"
KEY_FILE = Path(
    "C:/Users/VIKASHAN TECHNOLOGIE/AppData/Local/Temp/claude/"
    "d--Sumit-Projects-IntelliAI-Platform/67762b73-e6aa-43b8-a730-264d0d432d4f/"
    "scratchpad/m24-key.txt"
)
VALID = ROOT / "ml/datasets/data/indicvoices/hindi/valid"
MARKS = ("।", "?", ",")

CLIPS_SHORT = ["indicvoices-hindi-valid-0-000461.flac"]
CLIP_QUESTION = "indicvoices-hindi-valid-0-001485.flac"


def ffmpeg(*args: str) -> None:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args], check=True)  # noqa: S603,S607 — fixed argv, research instrument


def build_fixtures() -> None:
    SCRATCH.mkdir(parents=True, exist_ok=True)
    clips = sorted(VALID.glob("*.flac"))[:220]
    concat = SCRATCH / "concat.txt"
    concat.write_text("".join(f"file '{clip.as_posix()}'\n" for clip in clips), encoding="utf-8")
    long_wav = SCRATCH / "long-source.wav"
    ffmpeg(
        "-f", "concat", "-safe", "0", "-i", str(concat), "-ar", "16000", "-ac", "1", str(long_wav)
    )
    for name, seconds in (
        ("hi-5s", 5),
        ("hi-30s", 30),
        ("hi-120s", 120),
        ("hi-300s", 300),
        ("hi-600s", 600),
        ("hi-610s", 610),
    ):
        ffmpeg("-i", str(long_wav), "-t", str(seconds), str(SCRATCH / f"{name}.wav"))
    ffmpeg(
        "-i", str(VALID / CLIPS_SHORT[0]), "-ar", "16000", "-ac", "1", str(SCRATCH / "hi-short.wav")
    )
    ffmpeg(
        "-i",
        str(VALID / CLIP_QUESTION),
        "-ar",
        "16000",
        "-ac",
        "1",
        str(SCRATCH / "hi-question.wav"),
    )
    ffmpeg("-i", str(SCRATCH / "hi-short.wav"), "-c:a", "libopus", str(SCRATCH / "hi-short.webm"))
    ffmpeg(
        "-f", "lavfi", "-i", "anullsrc=r=16000:cl=mono", "-t", "6", str(SCRATCH / "silence-6s.wav")
    )
    ffmpeg(
        "-f",
        "lavfi",
        "-i",
        "anoisesrc=r=16000:colour=pink:amplitude=0.003",
        "-t",
        "6",
        "-ac",
        "1",
        str(SCRATCH / "noise-quiet-6s.wav"),
    )
    jfk = ROOT / "ml/evaluation/data/jfk-wav.wav"
    (SCRATCH / "en-jfk.wav").write_bytes(jfk.read_bytes())
    print(f"fixtures ready under {SCRATCH}")


def client() -> httpx.Client:
    key = max(KEY_FILE.read_text(encoding="utf-8").split(), key=len)
    return httpx.Client(
        base_url=BASE,
        verify=False,  # noqa: S501 — local Caddy self-signed edge, research instrument
        timeout=900.0,
        headers={"Authorization": f"Bearer {key}"},
    )


def transcribe(
    c: httpx.Client,
    path: Path,
    *,
    language: str | None = "hi",
    fmt: str | None = None,
    headers: dict[str, str] | None = None,
    mime: str = "audio/wav",
) -> httpx.Response:
    data: dict[str, str] = {"model": "intelliai-stt"}
    if language:
        data["language"] = language
    if fmt:
        data["response_format"] = fmt
    return c.post(
        "/v1/audio/transcriptions",
        files={"file": (path.name, path.read_bytes(), mime)},
        data=data,
        headers=headers or {},
    )


def has_marks(text: str) -> bool:
    return any(mark in text for mark in MARKS)


def run_battery() -> None:
    results: list[dict] = []

    def record(item: str, ok: bool, note: str = "") -> None:
        results.append({"item": item, "verdict": "PASS" if ok else "FAIL", "note": note})
        print(f"[{'PASS' if ok else 'FAIL'}] {item} {note[:110]}")

    with client() as c:
        # 1. Hindi normal speech → punctuated
        r = transcribe(c, SCRATCH / "hi-short.wav")
        text = r.json().get("text", "")
        record("hi-short punctuated", r.status_code == 200 and has_marks(text), text[:80])
        sample_id = r.headers.get("X-IntelliAI-Sample", "")

        # 2. English → whisper's own behavior, stage bypassed (no danda)
        r = transcribe(c, SCRATCH / "en-jfk.wav", language="en")
        text = r.json().get("text", "")
        record("en bypass (no danda)", r.status_code == 200 and "।" not in text, text[:80])

        # 3. Auto → default route, stage bypassed
        r = transcribe(c, SCRATCH / "hi-short.wav", language=None)
        record("auto no-language 200", r.status_code == 200, r.json().get("text", "")[:60])

        # 4-8. tiers (300s/600s exercise chunk-merge → punctuation-once)
        for name in ("hi-5s", "hi-30s", "hi-120s", "hi-300s", "hi-600s"):
            started = time.perf_counter()
            r = transcribe(c, SCRATCH / f"{name}.wav")
            wall = round(time.perf_counter() - started, 1)
            text = r.json().get("text", "") if r.status_code == 200 else ""
            record(
                f"{name} punctuated",
                r.status_code == 200 and has_marks(text),
                f"wall={wall}s enders={sum(text.count(m) for m in MARKS)}",
            )

        # 300s verbose_json: segment join law with punctuation on
        r = transcribe(c, SCRATCH / "hi-300s.wav", fmt="verbose_json")
        body = r.json()
        joined = " ".join(s["text"] for s in body.get("segments", []))
        record(
            "300s verbose_json join law",
            r.status_code == 200 and joined == body.get("text"),
            f"segments={len(body.get('segments', []))}",
        )

        # 9. >600s refused, zero billed
        r = transcribe(c, SCRATCH / "hi-610s.wav")
        record(">600s refused 400", r.status_code == 400, str(r.status_code))

        # 10-11. silence / quiet noise → empty, no punctuation
        for name in ("silence-6s", "noise-quiet-6s"):
            r = transcribe(c, SCRATCH / f"{name}.wav")
            text = r.json().get("text", "")
            record(f"{name} empty", r.status_code == 200 and text == "", repr(text[:40]))

        # 12. question clip (observational: does "?" arrive end-to-end)
        r = transcribe(c, SCRATCH / "hi-question.wav")
        text = r.json().get("text", "")
        record("question clip", r.status_code == 200 and text != "", text[:90])

        # 19-20. contribution ON (default) / OFF
        r = transcribe(c, SCRATCH / "hi-short.wav")
        record("contribution ON collects", "X-IntelliAI-Sample" in r.headers, "")
        r = transcribe(c, SCRATCH / "hi-short.wav", headers={"X-IntelliAI-Contribution": "off"})
        record("contribution OFF skips", "X-IntelliAI-Sample" not in r.headers, "")

        # 21. correction on the punctuated sample from drill 1
        if sample_id:
            r = c.post(
                f"/v1/audio/transcriptions/{sample_id}/correction",
                json={"corrected_text": "मैं ठीक हूँ!"},
            )
            record("correction 200", r.status_code == 200, "")
        else:
            record("correction 200", False, "no sample id from drill 1")

        # 22-24. client contract shapes → same punctuated output law
        texts = {}
        for label, headers, path, mime in (
            ("web", {"X-IntelliAI-Client": "web/1.0"}, SCRATCH / "hi-short.webm", "audio/webm"),
            (
                "android",
                {"X-IntelliAI-Client": "keyboard/1.6"},
                SCRATCH / "hi-short.wav",
                "audio/wav",
            ),
            (
                "ios",
                {"X-IntelliAI-Client": "ios-keyboard/1.0"},
                SCRATCH / "hi-short.wav",
                "audio/wav",
            ),
        ):
            r = transcribe(c, path, headers=headers, mime=mime)
            texts[label] = r.json().get("text", "")
            record(
                f"{label} client punctuated",
                r.status_code == 200 and has_marks(texts[label]),
                texts[label][:60],
            )
        record("android == ios output", texts.get("android") == texts.get("ios"), "")

        # 25. runtime restart → recovery with the stage intact
        subprocess.run(
            ["docker", "restart", "intelliai-stt-runtime-1"],  # noqa: S607
            check=True,
            capture_output=True,
        )
        deadline = time.time() + 300
        healthy = False
        while time.time() < deadline:
            probe = subprocess.run(
                ["docker", "inspect", "-f", "{{.State.Health.Status}}", "intelliai-stt-runtime-1"],  # noqa: S607
                capture_output=True,
                text=True,
                check=False,
            )
            if probe.stdout.strip() == "healthy":
                healthy = True
                break
            time.sleep(5)
        r = transcribe(c, SCRATCH / "hi-short.wav")
        text = r.json().get("text", "")
        record(
            "restart recovery punctuated",
            healthy and r.status_code == 200 and has_marks(text),
            text[:60],
        )

    (HERE / "staging-battery.json").write_text(
        json.dumps(
            {
                "experiment": "30-punctuation-runtime",
                "phase": "staging-battery",
                "results": results,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    failed = [r for r in results if r["verdict"] == "FAIL"]
    print(f"\n{len(results) - len(failed)}/{len(results)} PASS; failures: {len(failed)}")


def drill_disabled() -> None:
    """After restarting stt-runtime with the off-overlay: raw text expected."""
    with client() as c:
        r = transcribe(c, SCRATCH / "hi-short.wav")
        text = r.json().get("text", "")
        ok = r.status_code == 200 and text != "" and not has_marks(text)
        print(f"[{'PASS' if ok else 'FAIL'}] disable/rollback drill: raw text served: {text[:80]}")
        payload = {
            "item": "disable/rollback drill",
            "verdict": "PASS" if ok else "FAIL",
            "note": text[:100],
        }
        path = HERE / "staging-battery.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["results"].append(payload)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "run"
    if mode == "build-fixtures":
        build_fixtures()
    elif mode == "drill-disabled":
        drill_disabled()
    else:
        run_battery()
