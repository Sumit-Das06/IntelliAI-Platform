"""Media detection: magic bytes decide, extensions and claims never do."""

import pytest

from helpers import wav_bytes
from intelliai_runtime_contract import RuntimeErrorType
from intelliai_runtime_core import RuntimeServiceError
from intelliai_stt_runtime.pipeline import MediaFormat, detect_format


def test_wav_by_riff_header() -> None:
    assert detect_format(wav_bytes()) is MediaFormat.WAV


def test_flac_by_signature() -> None:
    assert detect_format(b"fLaC" + b"\x00" * 64) is MediaFormat.FLAC


def test_mp3_by_id3_and_frame_sync() -> None:
    assert detect_format(b"ID3\x04\x00" + b"\x00" * 64) is MediaFormat.MP3
    assert detect_format(b"\xff\xfb\x90\x00" + b"\x00" * 64) is MediaFormat.MP3


def test_ogg_by_signature() -> None:
    assert detect_format(b"OggS" + b"\x00" * 64) is MediaFormat.OGG


def test_webm_by_ebml_signature() -> None:
    assert detect_format(b"\x1a\x45\xdf\xa3" + b"\x00" * 64) is MediaFormat.WEBM


def test_mp4_by_ftyp_box() -> None:
    assert detect_format(b"\x00\x00\x00\x20ftypM4A " + b"\x00" * 64) is MediaFormat.MP4


def test_unrecognized_bytes_are_refused_before_any_subprocess() -> None:
    with pytest.raises(RuntimeServiceError) as exc_info:
        detect_format(b"definitely not audio at all")
    assert exc_info.value.error_type is RuntimeErrorType.INVALID_INPUT
    assert exc_info.value.param == "file"
