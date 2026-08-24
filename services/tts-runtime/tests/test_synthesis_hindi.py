# ruff: noqa: RUF001 - IPA and Devanagari glyphs are data, not typos.
"""M39 Hindi laws, proven without espeak or torch.

- **Parity**: the production component must reproduce the upstream
  misaki EspeakG2P(hi) output byte-for-byte from raw espeak-ng CLI
  lines (fixtures captured in the research venv against 1.51). A stub
  executable replays the recorded CLI lines, so the unit tier proves
  the TRANSFORM and the ASSEMBLY on any machine; the real binary is
  exercised by the docker smoke.
- **Danda chunking**: the M38 silent-truncation root cause — । and ॥
  are sentence boundaries now, Latin behavior byte-identical.
- **Routing**: a Hindi voice phonemizes through the Hindi component; an
  English voice keeps the M35 path; Hindi voices exist only when the
  deployment declares the component.
"""

import json
import stat
import sys
from pathlib import Path

import pytest

from intelliai_tts_runtime.config import Settings
from intelliai_tts_runtime.engines.espeak_hindi import (
    EspeakHindiG2P,
    HindiG2PError,
    map_hindi_ipa_to_kokoro,
)
from intelliai_tts_runtime.engines.kokoro import KokoroEngine, _chunks, _stream_chunks
from intelliai_tts_runtime.pipeline import TextPipeline
from intelliai_tts_runtime.slots import _kokoro_binding_for
from intelliai_tts_runtime.voices import KOKORO_VOICES, KOKORO_VOICES_WITH_HINDI

FIXTURES = json.loads(
    (Path(__file__).parent / "fixtures" / "hi_g2p_parity.json").read_text(encoding="utf-8")
)


def _write_replay_stub(tmp_path: Path) -> Path:
    """A stub espeak that replays the RECORDED CLI IPA line for every
    fixture segment — unknown lines echo marked, so a lookup miss is
    visible as a parity failure, never a silent pass."""
    table = {
        segment: ipa
        for row in FIXTURES["rows"]
        for segment, ipa in zip(row["segments"], row["cli_ipa_per_segment"], strict=True)
    }
    table_path = tmp_path / "replay-table.json"
    table_path.write_text(json.dumps(table, ensure_ascii=False), encoding="utf-8")
    stub = tmp_path / "espeak-stub"
    stub.write_text(
        f"""#!{sys.executable}
import json, sys
sys.stdout.reconfigure(encoding="utf-8")
sys.stdin.reconfigure(encoding="utf-8")
if "--version" in sys.argv:
    print("eSpeak NG text-to-speech: 1.51  Data at: /stub")
    sys.exit(0)
table = json.load(open({str(table_path)!r}, encoding="utf-8"))
for line in sys.stdin.read().splitlines():
    if line.strip():
        print(table.get(line.strip(), "MISS " + line.strip()))
""",
        encoding="utf-8",
    )
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
    if sys.platform == "win32":
        shim = tmp_path / "espeak-stub.bat"
        shim.write_text(f'@echo off\r\n"{sys.executable}" "{stub}" %*\r\n', encoding="utf-8")
        return shim
    return stub


class TestParity:
    def test_reproduces_upstream_output_on_every_fixture(self, tmp_path: Path) -> None:
        g2p = EspeakHindiG2P(
            _write_replay_stub(tmp_path), version_prefix="1.5", timeout_seconds=10.0
        )
        for row in FIXTURES["rows"]:
            assert g2p.phonemize(row["text"]) == row["expected_phonemes"], row["text"]

    def test_version_pin_refuses_a_wrong_phonemizer(self, tmp_path: Path) -> None:
        with pytest.raises(RuntimeError, match="does not match the pinned"):
            EspeakHindiG2P(_write_replay_stub(tmp_path), version_prefix="2.0", timeout_seconds=10.0)

    def test_missing_binary_refuses_loudly(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            EspeakHindiG2P(tmp_path / "nope", version_prefix="1.5", timeout_seconds=10.0)

    def test_subprocess_failure_raises_never_wrong_audio(self, tmp_path: Path) -> None:
        crash = tmp_path / "crash-stub"
        crash.write_text(
            f"#!{sys.executable}\nimport sys\n"
            'print("eSpeak NG text-to-speech: 1.51") if "--version" in sys.argv '
            "else sys.exit(3)\n",
            encoding="utf-8",
        )
        crash.chmod(crash.stat().st_mode | stat.S_IEXEC)
        if sys.platform == "win32":
            shim = tmp_path / "crash-stub.bat"
            shim.write_text(f'@echo off\r\n"{sys.executable}" "{crash}" %*\r\n', encoding="utf-8")
            crash = shim
        g2p = EspeakHindiG2P(crash, version_prefix="1.5", timeout_seconds=10.0)
        with pytest.raises(HindiG2PError):
            g2p.phonemize("नमस्ते।")


class TestMapping:
    @pytest.mark.parametrize(
        ("ipa", "expected"),
        [
            # language-switch flags stripped, English phonemes kept
            ("(en)ˈɒfɪs(hi) ɟˈaːnaː", "ˈɒfɪs ɟˈaːnaː"),
            # untied diphthongs (the CLI emits them bare)
            ("ˈeɪ ˈaɪ", "ˈA ˈI"),
            # tied affricate via the CLI's U+0361
            ("t͡ʃˈeːnɟ", "ʧˈeːnɟ"),
            # hyphens removed (upstream EspeakG2P rule)
            ("ɾˈʊk-ɟˈaːo", "ɾˈʊkɟˈaːo"),
            # Hindi keeps length marks and flaps — NO English US-branch rules
            ("mˌeːɾaː", "mˌeːɾaː"),
        ],
    )
    def test_transform_classes(self, ipa: str, expected: str) -> None:
        assert map_hindi_ipa_to_kokoro(ipa) == expected


class TestDandaChunking:
    def test_danda_is_a_sentence_boundary(self) -> None:
        text = "पहला वाक्य। दूसरा वाक्य। " + "लंबा शब्द " * 40
        chunks = list(_chunks(text))
        assert len(chunks) >= 2

    def test_danda_without_following_space_still_splits(self) -> None:
        sentence_a = "क" * 200 + "।"
        sentence_b = "ख" * 200 + "।"
        chunks = list(_chunks(sentence_a + sentence_b))
        assert chunks == [sentence_a, sentence_b]

    def test_double_danda_splits_too(self) -> None:
        # 181-char sentences cannot merge under the 300 budget, so each
        # ॥ boundary becomes its own chunk — three sentences, three chunks.
        chunks = list(_chunks(("ग" * 180 + "॥ ") * 3))
        assert len(chunks) == 3

    def test_no_text_is_lost_on_danda_paragraphs(self) -> None:
        text = " ".join("वाक्य संख्या " + "क" * 50 + "।" for _ in range(20))
        rejoined = " ".join(_chunks(text))
        assert rejoined.replace(" ", "") == text.replace(" ", "")

    def test_every_chunk_respects_the_budget(self) -> None:
        text = ("म" * 120 + "। ") * 30
        assert all(len(chunk) <= 300 for chunk in _chunks(text))

    def test_streaming_first_chunk_is_the_first_danda_sentence(self) -> None:
        text = "नमस्ते।" + " " + "बाकी लंबा पाठ " * 30
        first = next(_stream_chunks(text, 90))
        assert first == "नमस्ते।"

    def test_latin_sentence_behavior_is_unchanged(self) -> None:
        text = "One sentence. Two sentence! Three? " + "word " * 80
        assert list(_chunks(text)) == list(_chunks(text))  # deterministic
        # a Latin full stop with no following space still does NOT split —
        # the pre-M39 behavior, byte-identical (decimals stay whole).
        assert list(_chunks("Version 2.5 shipped")) == ["Version 2.5 shipped"]


class _FakeHindiG2P:
    version = "stub"

    def __init__(self) -> None:
        self.calls: list[str] = []

    def phonemize(self, text: str) -> str:
        self.calls.append(text)
        return "nəmˈʌsteː."


class _UnusedEnglishG2P:
    def __call__(self, chunk: str) -> tuple[str, list[object]]:
        raise AssertionError("a Hindi voice must never reach the English G2P")


class TestEngineRouting:
    def test_hindi_voice_rides_the_hindi_component(self) -> None:
        fake = _FakeHindiG2P()
        engine = KokoroEngine(
            model=None,
            g2p=_UnusedEnglishG2P(),
            voice_packs={},
            hindi_g2p=fake,  # type: ignore[arg-type]
        )
        assert engine._phonemize("नमस्ते।", "hi") == "nəmˈʌsteː."
        assert fake.calls == ["नमस्ते।"]

    def test_hindi_voice_without_component_is_a_wiring_error(self) -> None:
        engine = KokoroEngine(model=None, g2p=_UnusedEnglishG2P(), voice_packs={})
        with pytest.raises(RuntimeError, match="hindi"):
            engine._phonemize("नमस्ते।", "hi")


class TestVoiceGating:
    def test_declaring_the_component_serves_the_hindi_voices(self, tmp_path: Path) -> None:
        stub = _write_replay_stub(tmp_path)
        settings = Settings(slots="kokoro", hindi_g2p="espeak", espeak_binary=stub.resolve())
        binding = _kokoro_binding_for(settings)
        assert binding.voices is KOKORO_VOICES_WITH_HINDI
        assert set(binding.voices.bindings) >= {"hindi-female", "hindi-male"}
        assert binding.voices.language_of("hindi-female") == "hi"
        assert binding.voices.language_of("english-female") == "en"

    def test_default_deployment_serves_no_hindi_voice(self) -> None:
        binding = _kokoro_binding_for(Settings(slots="kokoro"))
        assert binding.voices is KOKORO_VOICES
        assert "hindi-female" not in binding.voices.bindings

    def test_missing_binary_refuses_startup(self, tmp_path: Path) -> None:
        settings = Settings(
            slots="kokoro", hindi_g2p="espeak", espeak_binary=(tmp_path / "nope").resolve()
        )
        with pytest.raises(FileNotFoundError):
            _kokoro_binding_for(settings)

    def test_hindi_voice_ids_never_name_engine_tokens(self) -> None:
        for public_id in KOKORO_VOICES_WITH_HINDI.bindings:
            assert "hf_" not in public_id
            assert "hm_" not in public_id
            assert "kokoro" not in public_id
            assert "espeak" not in public_id


class TestPipelineLanguageRouting:
    def test_hindi_voice_reads_hindi_rules(self) -> None:
        pipeline = TextPipeline(max_text_chars=2000)
        assert "रुपये" in pipeline.process("इसकी कीमत ₹12,500 है।", "hi").text
        assert "rupees" not in pipeline.process("इसकी कीमत ₹12,500 है।", "hi").text

    def test_english_stays_the_m35_pack(self) -> None:
        pipeline = TextPipeline(max_text_chars=2000)
        assert pipeline.process("Pay ₹12,500 now.").text == "Pay 12500 rupees now."
