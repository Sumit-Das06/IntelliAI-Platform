"""Sample GPU VRAM/utilization while a battery runs.

python gpu_sample.py <seconds> <out.json>
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

EVIDENCE = Path(__file__).resolve().parent / "evidence"
NVIDIA_SMI = shutil.which("nvidia-smi") or "nvidia-smi"


def main() -> None:
    seconds, out_name = float(sys.argv[1]), sys.argv[2]
    rows = []
    deadline = time.time() + seconds
    while time.time() < deadline:
        query = [
            NVIDIA_SMI,
            "--query-gpu=memory.used,utilization.gpu",
            "--format=csv,noheader,nounits",
        ]
        out = subprocess.check_output(query).decode().strip()  # noqa: S603 — fixed argv
        vram, util = (int(x) for x in out.split(","))
        rows.append({"t": round(time.time(), 1), "vram_mib": vram, "util_pct": util})
        time.sleep(2)
    vrams = [row["vram_mib"] for row in rows]
    utils = [row["util_pct"] for row in rows]
    result = {
        "samples": len(rows),
        "vram_mib_min": min(vrams),
        "vram_mib_max": max(vrams),
        "util_pct_max": max(utils),
        "rows": rows[:: max(1, len(rows) // 60)],
    }
    (EVIDENCE / out_name).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}))


if __name__ == "__main__":
    main()
