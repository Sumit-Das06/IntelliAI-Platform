"""The speech-eval CLI: corpus + two live URLs -> one evidence record.

Stub HTTP servers stand in for the runtimes (CI has no models), speaking
just enough of the two bindings: /info on both, WAV body from
/v1/synthesize, a JSON envelope from /v1/transcribe. What the test pins:
the command produces a schema-valid record whose reproducibility
metadata came from LIVE /info facts, and it REFUSES to run when the
runtime is not serving the artifact named.
"""

import datetime
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from intelliai_evaluation.cli import main
from intelliai_evaluation.corpus import (
    CorpusProvenance,
    Difficulty,
    SpeechCorpus,
    SpeechTextCase,
    TextCategory,
)
from intelliai_evaluation.speech_results import SpeechEvalRun
from test_signal import tone, wav_of

WAV = wav_of(tone(1.0))


def corpus_file(tmp_path: Path) -> Path:
    corpus = SpeechCorpus(
        name="cli-demo",
        version=1,
        provenance=CorpusProvenance(
            author="tests",
            created=datetime.date(2026, 8, 3),
            rationale="cli integration",
            source="synthetic",
            languages=("en",),
        ),
        cases=(
            SpeechTextCase(
                id="case-a",
                language="en",
                category=TextCategory.GENERAL,
                difficulty=Difficulty.EASY,
                text="hello evaluation world",
            ),
        ),
    )
    path = tmp_path / "corpus.json"
    path.write_text(corpus.model_dump_json(), encoding="utf-8")
    return path


class _FakeTts(BaseHTTPRequestHandler):
    def log_message(self, *args: object) -> None:  # keep test output clean
        return

    def do_GET(self) -> None:
        body = json.dumps(
            {
                "service": "tts-runtime",
                "service_version": "9.9.9",
                "models": [{"slot": "default", "artifact": "fake-tts"}],
            }
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        self.rfile.read(int(self.headers.get("Content-Length", "0")))
        self.send_response(200)
        self.send_header("Content-Type", "audio/wav")
        self.end_headers()
        self.wfile.write(WAV)


class _FakeStt(BaseHTTPRequestHandler):
    def log_message(self, *args: object) -> None:
        return

    def do_GET(self) -> None:
        body = json.dumps({"service": "stt-runtime", "service_version": "8.8.8"}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        self.rfile.read(int(self.headers.get("Content-Length", "0")))
        body = json.dumps({"output": {"text": "hello evaluation world"}}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)


def serve(handler: type[BaseHTTPRequestHandler]) -> tuple[ThreadingHTTPServer, str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_port}"


def speech_eval_args(corpus: Path, tts_url: str, stt_url: str, out: Path) -> list[str]:
    return [
        "speech-eval",
        "--corpus",
        str(corpus),
        "--tts-url",
        tts_url,
        "--stt-url",
        stt_url,
        "--artifact",
        "fake-tts",
        "--lineage",
        "fake",
        "--voice",
        "reference-alto",
        "--hardware",
        "test machine",
        "--out",
        str(out),
    ]


def test_cli_produces_schema_valid_evidence_from_live_facts(tmp_path: Path) -> None:
    tts_server, tts_url = serve(_FakeTts)
    stt_server, stt_url = serve(_FakeStt)
    out = tmp_path / "results" / "run.json"
    try:
        exit_code = main(speech_eval_args(corpus_file(tmp_path), tts_url, stt_url, out))
    finally:
        tts_server.shutdown()
        stt_server.shutdown()
    assert exit_code == 0
    run = SpeechEvalRun.model_validate_json(out.read_text(encoding="utf-8"))
    # Reproducibility metadata came from the LIVE runtimes, not CLI claims.
    assert run.runtime.service_version == "9.9.9"
    assert run.judge.runtime_version == "8.8.8"
    assert run.synthesis_params == {"voice": "reference-alto"}
    assert run.aggregate_metrics["round_trip_wer"] == 0.0
    assert run.baseline_name is None  # a baseline must be christened explicitly


def test_cli_refuses_when_runtime_serves_a_different_artifact(tmp_path: Path) -> None:
    tts_server, tts_url = serve(_FakeTts)
    stt_server, stt_url = serve(_FakeStt)
    out = tmp_path / "run.json"
    args = speech_eval_args(corpus_file(tmp_path), tts_url, stt_url, out)
    args[args.index("fake-tts")] = "kokoro-82m"  # operator names the wrong subject
    try:
        exit_code = main(args)
    finally:
        tts_server.shutdown()
        stt_server.shutdown()
    assert exit_code == 2  # a record that misnames its subject would poison the ledger
    assert not out.exists()
