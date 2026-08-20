# ruff: noqa: RUF001, RUF003 - IPA glyphs are phoneme data, not lookalike typos.
"""M35 OOV-fallback laws, proven without espeak: a stub executable plays
the binary so the unit tier tests the BOUNDARY — argv constancy, stdin
transport, timeout, version pinning, failure-safety, splice order — on
any machine. The real binary is exercised by the docker smoke."""

import stat
import sys
from pathlib import Path

import pytest

from intelliai_tts_runtime.engines.espeak_fallback import (
    EspeakSubprocessFallback,
    map_ipa_to_kokoro,
)
from intelliai_tts_runtime.engines.kokoro import KokoroEngine

_STUB = """#!{python}
import sys
sys.stdout.reconfigure(encoding="utf-8")
lines = sys.stdin.read().splitlines()
if "--version" in sys.argv:
    print("eSpeak NG text-to-speech: 1.51  Data at: /stub")
    sys.exit(0)
for line in lines:
    if line.strip():
        print("st\\u02c8\\u028cb " + line.strip().lower())
"""


def _write_stub(tmp_path: Path, body: str | None = None) -> Path:
    stub = tmp_path / "espeak-stub"
    stub.write_text(body or _STUB.format(python=sys.executable), encoding="utf-8")
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
    if sys.platform == "win32":
        # Windows cannot exec a shebang script; wrap through a .bat shim.
        shim = tmp_path / "espeak-stub.bat"
        shim.write_text(f'@echo off\r\n"{sys.executable}" "{stub}" %*\r\n', encoding="utf-8")
        return shim
    return stub


class TestBoundary:
    def test_version_pin_accepts_matching_binary(self, tmp_path: Path) -> None:
        fallback = EspeakSubprocessFallback(
            _write_stub(tmp_path), version_prefix="1.5", timeout_seconds=10.0
        )
        assert fallback.version.startswith("1.5")

    def test_version_pin_refuses_a_wrong_phonemizer(self, tmp_path: Path) -> None:
        with pytest.raises(RuntimeError, match="does not match the pinned"):
            EspeakSubprocessFallback(
                _write_stub(tmp_path), version_prefix="2.0", timeout_seconds=10.0
            )

    def test_missing_binary_refuses_loudly(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            EspeakSubprocessFallback(tmp_path / "nope", version_prefix="1.5", timeout_seconds=10.0)

    def test_relative_path_is_refused(self) -> None:
        with pytest.raises(ValueError, match="absolute"):
            EspeakSubprocessFallback(Path("espeak-ng"), version_prefix="1.5", timeout_seconds=10.0)

    def test_words_travel_via_stdin_one_line_each(self, tmp_path: Path) -> None:
        fallback = EspeakSubprocessFallback(
            _write_stub(tmp_path), version_prefix="1.5", timeout_seconds=10.0
        )
        result = fallback.phonemize_words(["Kavya", "IntelliAI"])
        assert set(result) == {"Kavya", "IntelliAI"}
        assert all(value for value in result.values())

    def test_hostile_text_never_becomes_an_argument(self, tmp_path: Path) -> None:
        # Shell metacharacters and option-shaped words are DATA on stdin;
        # newlines and NULs are dropped before the boundary entirely.
        fallback = EspeakSubprocessFallback(
            _write_stub(tmp_path), version_prefix="1.5", timeout_seconds=10.0
        )
        hostile = ["--help", "-v; rm -rf /", "$(reboot)", "a\nb", "nul\x00byte", "x" * 500]
        result = fallback.phonemize_words(hostile)
        assert set(result) <= {"--help", "-v; rm -rf /", "$(reboot)"}

    def test_failure_returns_empty_never_raises(self, tmp_path: Path) -> None:
        crash = _write_stub(
            tmp_path,
            f"#!{sys.executable}\nimport sys\n"
            'print("eSpeak NG text-to-speech: 1.51") if "--version" in sys.argv '
            "else sys.exit(3)\n",
        )
        fallback = EspeakSubprocessFallback(crash, version_prefix="1.5", timeout_seconds=10.0)
        assert fallback.phonemize_words(["word"]) == {}


class TestIpaMapping:
    @pytest.mark.parametrize(
        ("ipa", "expected"),
        [
            ("kˈɑːvjə", "kˈɑvjə"),  # length mark dropped (US branch)
            ("ɪntˌɛlɪdʒˈeɪ", "ɪntˌɛlɪʤˈA"),  # tied dʒ + eɪ diphthong (CLI tie)
            ("hˈaɪ", "hˈI"),  # aɪ -> I
            ("(en)wˈɜːd", "wˈɜɹd"),  # switch-marker stripped, ɜː -> ɜɹ
        ],
    )
    def test_transform_classes_measured_in_m32(self, ipa: str, expected: str) -> None:
        cli_form = ipa.replace("dʒ", "d͡ʒ").replace("eɪ", "e͡ɪ").replace("aɪ", "a͡ɪ")
        assert map_ipa_to_kokoro(cli_form) == expected


class _Token:
    def __init__(self, text: str, phonemes: str | None, whitespace: str = " ") -> None:
        self.text = text
        self.phonemes = phonemes
        self.whitespace = whitespace


class _FakeG2P:
    """misaki's observed contract: (phoneme_string, tokens); unknown words
    carry phonemes=None (whole-word) or an embedded ❓ (partial)."""

    def __call__(self, chunk: str) -> tuple[str, list[_Token]]:
        tokens = [
            _Token("Welcome", "wˈɛlkəm"),
            _Token("IntelliAI", "❓ˈAˌI"),
            _Token("Kavya", None, ""),  # word directly before punctuation
            _Token(".", ".", ""),
        ]
        return "wˈɛlkəm ❓ˈAˌI ❓.", tokens


class _FakeFallback:
    version = "stub"

    def __init__(self, answers: dict[str, str]) -> None:
        self.answers = answers
        self.calls: list[list[str]] = []

    def phonemize_words(self, words: list[str]) -> dict[str, str]:
        self.calls.append(words)
        return {word: self.answers[word] for word in words if word in self.answers}


class TestSplice:
    def _engine(self, fallback: _FakeFallback | None) -> KokoroEngine:
        return KokoroEngine(model=None, g2p=_FakeG2P(), voice_packs={}, oov_fallback=fallback)  # type: ignore[arg-type]

    def test_unknown_tokens_are_rescued_in_token_order(self) -> None:
        fallback = _FakeFallback({"IntelliAI": "ɪntɛlɪʤˈA", "Kavya": "kˈɑvjə"})
        engine = self._engine(fallback)
        assert engine._phonemize("x") == "wˈɛlkəm ɪntɛlɪʤˈA kˈɑvjə."
        assert fallback.calls == [["IntelliAI", "Kavya"]]  # deduped, sorted, one call

    def test_partial_rescue_keeps_the_rest_dictionary_only(self) -> None:
        engine = self._engine(_FakeFallback({"Kavya": "kˈɑvjə"}))
        assert engine._phonemize("x") == "wˈɛlkəm ❓ˈAˌI kˈɑvjə."

    def test_fallback_failure_degrades_to_dictionary_behavior(self) -> None:
        engine = self._engine(_FakeFallback({}))
        assert engine._phonemize("x") == "wˈɛlkəm ❓ˈAˌI ❓."

    def test_disabled_fallback_is_exactly_v1(self) -> None:
        engine = self._engine(None)
        assert engine._phonemize("x") == "wˈɛlkəm ❓ˈAˌI ❓."
