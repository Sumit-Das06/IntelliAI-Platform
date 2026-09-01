"""M56 isolated prototype — run the frozen benchmark through a local
llama-server candidate. RESEARCH ONLY: no production API, no Playground,
no DB, no user data; loopback llama-server only.

    python run_correction.py --url http://127.0.0.1:8899 \
        --model-name qwen3-4b-instruct-q4km \
        --dataset <dataset.jsonl> --out <outputs.jsonl> [--limit N] [--language en|hi]
"""

# ruff: noqa: T201 — research scripts report via stdout

from __future__ import annotations

import argparse
import json
import statistics
import time
import urllib.request
from pathlib import Path

_HERE = Path(__file__).resolve().parent
PROMPT = (_HERE / "prompt_contract.txt").read_text(encoding="utf-8")
PROMPTS = {
    "en": (_HERE / "prompt_en.txt").read_text(encoding="utf-8"),
    "hi": (_HERE / "prompt_hi.txt").read_text(encoding="utf-8"),
}


def correct(url: str, text: str, timeout: float = 120.0, language: str = "") -> tuple[str, float]:
    prompt = PROMPTS.get(language, PROMPT)
    payload = {
        "messages": [
            {"role": "system", "content": prompt + "\n/no_think"},
            {"role": "user", "content": text},
        ],
        "temperature": 0.0,
        "max_tokens": max(96, min(1024, len(text.split()) * 4 + 64)),
    }
    request = urllib.request.Request(  # noqa: S310 — loopback research server
        f"{url}/v1/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        body = json.loads(response.read())
    latency_ms = (time.perf_counter() - started) * 1000.0
    out = str(body["choices"][0]["message"]["content"]).strip()
    # Qwen3 hybrid models may emit an empty think block even with /no_think.
    if "</think>" in out:
        out = out.rsplit("</think>", 1)[1].strip()
    return out, round(latency_ms, 1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--model-name", required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--language", default="")
    args = parser.parse_args()

    rows = [json.loads(line) for line in args.dataset.read_text(encoding="utf-8").splitlines()]
    if args.language:
        rows = [row for row in rows if row["language"] == args.language]
    if args.limit:
        rows = rows[: args.limit]

    latencies: list[float] = []
    with args.out.open("w", encoding="utf-8") as sink:
        for i, row in enumerate(rows):
            output, latency_ms = correct(args.url, row["noisy_input"], language=row["language"])
            latencies.append(latency_ms)
            sink.write(
                json.dumps(
                    {
                        "id": row["id"],
                        "model": args.model_name,
                        "output": output,
                        "latency_ms": latency_ms,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            if (i + 1) % 25 == 0:
                print(f"{i + 1}/{len(rows)} p50={statistics.median(latencies):.0f}ms", flush=True)
    print(
        json.dumps(
            {
                "model": args.model_name,
                "rows": len(rows),
                "latency_p50_ms": round(statistics.median(latencies), 1),
                "latency_p95_ms": round(sorted(latencies)[int(0.95 * (len(latencies) - 1))], 1),
            }
        )
    )


if __name__ == "__main__":
    main()
