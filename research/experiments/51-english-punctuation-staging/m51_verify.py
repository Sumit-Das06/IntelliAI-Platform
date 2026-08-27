"""M51 offline cross-checks over the captured browser evidence.

Proves, from the recorded DOM text alone:
  - word invariant between the flag-ON and flag-OFF boss runs,
  - flag-OFF == forced-timeout fail-open output (both raw, byte-equal),
  - recovery run punctuated again after the rollback drill,
  - share clipboard == displayed transcript,
  - correction started from the displayed text,
  - mobile/tablet usability flags,
  - no security problems recorded.

    python m51_verify.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
EVIDENCE = HERE / "evidence"
sys.path.insert(0, str(ROOT / "services/stt-runtime/src"))

from intelliai_stt_runtime.engines.punctuation import depunct  # noqa: E402


def load(name: str) -> dict:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def main() -> None:
    on = load("browser-e2e-on.json")
    off = load("browser-off.json")
    failopen = load("browser-failopen.json")
    recovered = load("browser-recovered.json")

    boss_on = on["runs"][0]["displayed_text"]
    boss_off = off["runs"][0]["displayed_text"]
    boss_failopen = failopen["runs"][0]["displayed_text"]
    boss_recovered = recovered["runs"][0]["displayed_text"]

    checks = {
        "boss_word_invariant_on_vs_off": depunct(boss_on) == depunct(boss_off),
        "boss_on_is_punctuated": boss_on != boss_off and ("." in boss_on or "," in boss_on),
        "flag_off_equals_failopen_byte_for_byte": boss_off == boss_failopen,
        "flag_off_has_no_v1_marks": not any(mark in boss_off for mark in ".,?"),
        "recovered_equals_on_run": depunct(boss_recovered) == depunct(boss_on),
        "recovered_is_punctuated": "." in boss_recovered or "," in boss_recovered,
        "share_clipboard_equals_displayed": on["share"]["clipboard_equals_displayed"],
        "correction_started_from_displayed": on["correction"]["started_from_displayed"],
        "correction_acknowledged": bool(on["correction"]["thanks_line"]),
        "mobile_usable": all(
            on["mobile"][key]
            for key in (
                "share_visible",
                "transcript_visible",
                "no_horizontal_scroll",
            )
        ),
        "tablet_no_horizontal_scroll": on["tablet_no_horizontal_scroll"],
        "security_problems": on["problems"],
        "status_page_makes_no_production_claim": not on["status_page_mentions_production_claim"],
        "hindi_display": on["runs"][-1]["displayed_text"],
        "hindi_has_no_latin_period_burst": ".." not in on["runs"][-1]["displayed_text"],
    }
    battery = {
        run["clip"]: run["displayed_text"]
        for run in on["runs"]
        if run["clip"].endswith(".wav") and run["language"] == "en"
    }
    checks["battery_no_double_marks"] = not any(
        ".." in text or ",," in text or "??" in text for text in battery.values()
    )

    payload = {"checks": checks, "battery_displayed": battery}
    (EVIDENCE / "verification.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    failures = [
        key
        for key, value in checks.items()
        if value is False and key != "status_page_mentions_production_claim"
    ]
    if checks["security_problems"]:
        failures.append("security_problems")
    print("FAILURES:", failures or "none")
    for key, value in checks.items():
        if key not in ("hindi_display",):
            print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
