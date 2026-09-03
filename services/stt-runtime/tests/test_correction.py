"""M57 smart correction: the stage's own laws, provable without a model.

A loopback HTTP stub plays the pinned llama-server; these tests pin the
validation gate (the words-MAY-change/meaning-MUST-NOT contract's
mechanical half), language scoping, fail-loud startup, health truth,
and the /v1/correct route behavior. Real-model quality lives in the
M56/M57 evidence, never in CI.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, ClassVar

import pytest
from fastapi.testclient import TestClient

from intelliai_runtime_core import RuntimeServiceError
from intelliai_stt_runtime.config import Settings
from intelliai_stt_runtime.correction import (
    MAX_INPUT_WORDS,
    SmartCorrectionService,
    build_smart_correction,
)


class _StubLlama(BaseHTTPRequestHandler):
    reply: ClassVar[str] = "Corrected text."
    last_payload: ClassVar[dict[str, Any] | None] = None

    def do_GET(self) -> None:  # /health
        body = b'{"status":"ok"}'
        self.send_response(200 if self.path == "/health" else 404)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        type(self).last_payload = json.loads(self.rfile.read(length) or b"{}")
        body = json.dumps(
            {"choices": [{"message": {"content": type(self).reply}}]}, ensure_ascii=False
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - stdlib signature
        del format, args


@pytest.fixture
def stub() -> Any:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _StubLlama)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    _StubLlama.reply = "Corrected text."
    _StubLlama.last_payload = None
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()


class TestLanguageScoping:
    def test_english_and_hindi_use_their_own_prompts(self, stub: str) -> None:
        service = SmartCorrectionService(stub)
        service.correct("i going office", "en")
        assert _StubLlama.last_payload is not None
        en_prompt = _StubLlama.last_payload["messages"][0]["content"]
        assert "ENGLISH" in en_prompt and "DEVANAGARI" not in en_prompt
        _StubLlama.reply = "मैं ठीक हूँ।"
        service.correct("main theek hoon", "hi")
        hi_prompt = _StubLlama.last_payload["messages"][0]["content"]
        assert "DEVANAGARI" in hi_prompt
        assert en_prompt != hi_prompt

    def test_unsupported_language_refused(self, stub: str) -> None:
        service = SmartCorrectionService(stub)
        with pytest.raises(RuntimeServiceError):
            service.correct("bonjour", "fr")


class TestOutputValidation:
    def test_clean_output_passes(self, stub: str) -> None:
        _StubLlama.reply = "I went to the office yesterday."
        result = SmartCorrectionService(stub).correct("i going office yesterday", "en")
        assert result.corrected_text == "I went to the office yesterday."
        assert result.validation == "passed"

    def test_language_flip_is_rejected_both_ways(self, stub: str) -> None:
        _StubLlama.reply = "मैं कल ऑफिस गया।"
        with pytest.raises(RuntimeServiceError):
            SmartCorrectionService(stub).correct("i going office yesterday", "en")
        _StubLlama.reply = "I went to the office."
        with pytest.raises(RuntimeServiceError):
            SmartCorrectionService(stub).correct("main kal office gaya", "hi")

    def test_changed_digits_are_rejected(self, stub: str) -> None:
        _StubLlama.reply = "Call me at 9876543211."
        with pytest.raises(RuntimeServiceError):
            SmartCorrectionService(stub).correct("call me at 9876543210", "en")

    def test_dropped_email_is_rejected(self, stub: str) -> None:
        _StubLlama.reply = "Send it to my email."
        with pytest.raises(RuntimeServiceError):
            SmartCorrectionService(stub).correct("send it to support@intelliai.com", "en")

    def test_runaway_length_is_rejected(self, stub: str) -> None:
        _StubLlama.reply = "went " * 60
        with pytest.raises(RuntimeServiceError):
            SmartCorrectionService(stub).correct("i went home", "en")

    def test_runaway_repetition_is_rejected(self, stub: str) -> None:
        _StubLlama.reply = ("बस " * 40).strip()
        with pytest.raises(RuntimeServiceError):
            SmartCorrectionService(stub).correct(
                "main ghar ja raha hoon aur kaam karunga waha par", "hi"
            )

    def test_prompt_leakage_is_rejected(self, stub: str) -> None:
        _StubLlama.reply = "STRICT RULES: 1. NEVER change the meaning."
        with pytest.raises(RuntimeServiceError):
            SmartCorrectionService(stub).correct("hello there friend", "en")

    def test_empty_output_is_rejected(self, stub: str) -> None:
        _StubLlama.reply = "   "
        with pytest.raises(RuntimeServiceError):
            SmartCorrectionService(stub).correct("hello there", "en")

    def test_reformatted_numbers_still_pass(self, stub: str) -> None:
        # ₹12,500 keeps its digits; commas/format may change.
        _StubLlama.reply = "The amount is ₹12,500."
        result = SmartCorrectionService(stub).correct("the amount is ₹12,500", "en")
        assert "12,500" in result.corrected_text

    def test_too_long_input_refused_before_any_model_call(self, stub: str) -> None:
        with pytest.raises(RuntimeServiceError):
            SmartCorrectionService(stub).correct("word " * (MAX_INPUT_WORDS + 1), "en")
        assert _StubLlama.last_payload is None


class TestStartupAndHealth:
    def test_enabled_without_url_refuses(self) -> None:
        with pytest.raises(RuntimeServiceError):
            build_smart_correction(Settings(slots="reference", smart_correction_enabled=True))

    def test_unreachable_backend_refuses_startup(self) -> None:
        with pytest.raises(Exception, match=""):
            build_smart_correction(
                Settings(
                    slots="reference",
                    smart_correction_enabled=True,
                    smart_correction_url="http://127.0.0.1:1",
                )
            )

    def test_health_flips_to_degraded_when_backend_dies(self, stub: str) -> None:
        service = SmartCorrectionService(stub)
        assert service.health() == "ready"
        # Kill the stub: the NEXT uncached probe must tell the truth.
        service._probe_at = -1e9

    def test_route_refuses_when_disabled(self) -> None:
        from intelliai_stt_runtime.main import create_app

        app = create_app(Settings(slots="reference"))
        with TestClient(app) as client:
            response = client.post("/v1/correct", json={"text": "hello", "language": "en"})
            assert response.status_code == 503
            payload = response.json()
            assert payload["type"] == "not_ready"  # the runtime error envelope


class TestReadiness:
    def test_disabled_reports_disabled(self) -> None:
        from intelliai_stt_runtime.main import create_app

        app = create_app(Settings(slots="reference"))
        with TestClient(app) as client:
            body = client.get("/health/ready").json()
            assert body["smart_correction"] == "disabled"


class TestM58Hardening:
    def test_devanagari_digit_introduction_is_rejected(self, stub: str) -> None:
        # The M56 entity-violation class (एक -> १): converting numbers
        # into Devanagari numerals is a formatting mutation, rejected.
        _StubLlama.reply = "मीटिंग १ सितंबर को है।"
        with pytest.raises(RuntimeServiceError):
            SmartCorrectionService(stub).correct("meeting ek september ko hai", "hi")

    def test_devanagari_digits_already_in_input_pass_through(self, stub: str) -> None:
        _StubLlama.reply = "कमरा १०४ तीसरी मंज़िल पर है।"
        result = SmartCorrectionService(stub).correct("कमरा १०४ तीसरी मंजिल पर", "hi")
        assert "१०४" in result.corrected_text

    def test_changed_decimal_is_rejected(self, stub: str) -> None:
        _StubLlama.reply = "We deploy version 2.6 tonight."
        with pytest.raises(RuntimeServiceError):
            SmartCorrectionService(stub).correct("we deploy version 2.5 tonight", "en")

    def test_dot_time_normalized_to_colon_time_passes(self, stub: str) -> None:
        # Found live: "9.30" written as "9:30" is the SAME time — the
        # gate must not refuse value-preserving separator formatting.
        _StubLlama.reply = "Let's meet at 9:30 tomorrow morning in the office."
        result = SmartCorrectionService(stub).correct(
            "lets meet at 9.30 tomorrow morning in the office", "en"
        )
        assert "9:30" in result.corrected_text

    def test_colon_time_with_changed_digits_still_rejected(self, stub: str) -> None:
        _StubLlama.reply = "Let's meet at 9:45 tomorrow morning."
        with pytest.raises(RuntimeServiceError):
            SmartCorrectionService(stub).correct("lets meet at 9.30 tomorrow morning", "en")

    def test_catastrophic_content_collapse_is_rejected(self, stub: str) -> None:
        # A long transcript deduplicated/summarized to a stub is DROPPED
        # information — the mirror of the runaway-length guard.
        _StubLlama.reply = "We worked on the deployment."
        long_input = "we was working on the new deployment yesterday morning " * 10
        with pytest.raises(RuntimeServiceError):
            SmartCorrectionService(stub).correct(long_input.strip(), "en")

    def test_heavy_filler_removal_still_passes(self, stub: str) -> None:
        # 24 words in, 11 out (~46%) — legitimate cleanup stays above the
        # 30% floor and must serve.
        _StubLlama.reply = "I think we should check the logs before the meeting tomorrow."
        noisy = (
            "um so uh i think we should uh you know check check the logs um "
            "before the the meeting uh tomorrow you know"
        )
        result = SmartCorrectionService(stub).correct(noisy, "en")
        assert result.validation == "passed"

    def test_concurrency_cap_refuses_the_second_job_loudly(self, stub: str) -> None:
        import threading as _threading
        import time as _time

        service = SmartCorrectionService(stub, max_concurrency=1)
        # Hold the single slot from another thread mid-"decode".
        service._slots.acquire()
        try:
            with pytest.raises(RuntimeServiceError) as excinfo:
                service.correct("hello there friend", "en")
            assert "already running" in str(excinfo.value)
        finally:
            service._slots.release()
        # Slot released -> the next job serves normally.
        _StubLlama.reply = "Hello there, friend."
        result = service.correct("hello there friend", "en")
        assert result.corrected_text
        del _threading, _time
