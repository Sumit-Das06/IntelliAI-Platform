"""M32 — license-path parity probe: espeak-ng SUBPROCESS vs in-process GPL chain.

The M3 license review named subprocess-isolated phonemization (the ffmpeg posture:
GPL *binary* behind an exec boundary) as one of the two compliant Hindi paths. This
probe measures whether that path is a faithful stand-in for what the upstream
pipeline does in-process:

  library path   misaki.espeak.EspeakG2P("hi")  (phonemizer-fork + espeakng-loader,
                 GPL chain IN-PROCESS - research venv only, never production)
  subprocess     the espeak-ng CLI binary, exec boundary, no linking

For every Hindi probe text both phoneme strings are produced and compared. Where
they differ, the diff is recorded verbatim — differences mean the production
implementation must pin the same espeak-ng build and replicate the wrapper's
post-processing, and the remaining delta feeds the M32 report, not a hand-wave.

Run inside the kokoro research venv (WSL):
    python espeak_parity_probe.py --probes probe-texts-v1.json --out parity.json
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


def cli_phonemes(text: str, espeak_binary: str, voice: str = "hi") -> str:
    """Phonemize via the espeak-ng BINARY (exec boundary — the compliant shape).

    Flags mirror what phonemizer's library backend requests: IPA output with
    stress marks, no audio, one line per input line.
    """
    completed = subprocess.run(  # noqa: S603 - fixed argv, research instrument
        [espeak_binary, "-q", "--ipa", "-v", voice, text],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return " ".join(completed.stdout.split())


def library_phonemes(text: str) -> str:
    from misaki import espeak

    g2p = library_phonemes.cache.get("g2p")  # type: ignore[attr-defined]
    if g2p is None:
        g2p = espeak.EspeakG2P(language="hi")
        library_phonemes.cache["g2p"] = g2p  # type: ignore[attr-defined]
    phonemes, _ = g2p(text)
    return " ".join(str(phonemes).split())


library_phonemes.cache = {}  # type: ignore[attr-defined]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--probes", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--espeak-binary", default="espeak-ng")
    args = parser.parse_args()

    probes = json.loads(Path(args.probes).read_text(encoding="utf-8"))["cases"]
    hindi = [case for case in probes if case["language"] in ("hi", "mixed")]

    cli_version = subprocess.run(  # noqa: S603 - fixed argv
        [args.espeak_binary, "--version"], capture_output=True, text=True, check=True
    ).stdout.strip()
    import espeakng_loader

    library_data = str(espeakng_loader.get_data_path())

    rows: list[dict[str, object]] = []
    matches = 0
    for case in hindi:
        text = case["text"]
        via_cli = cli_phonemes(text, args.espeak_binary)
        via_library = library_phonemes(text)
        matched = via_cli == via_library
        matches += int(matched)
        row: dict[str, object] = {"id": case["id"], "match": matched}
        if not matched:
            row["cli"] = via_cli
            row["library"] = via_library
        rows.append(row)

    report = {
        "experiment": "32-tts-model-selection",
        "instrument": "espeak_parity_probe.py",
        "question": (
            "is subprocess espeak-ng (exec boundary, GPL-clean like ffmpeg) a faithful "
            "stand-in for the in-process GPL chain the upstream Hindi pipeline uses?"
        ),
        "cli_version": cli_version,
        "library_espeak_data": library_data,
        "texts": len(rows),
        "exact_matches": matches,
        "match_rate": round(matches / len(rows), 4) if rows else None,
        "rows": rows,
    }
    Path(args.out).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"parity: {matches}/{len(rows)} exact matches ({report['match_rate']})")


if __name__ == "__main__":
    main()
