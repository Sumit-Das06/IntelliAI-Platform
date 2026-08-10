"""Offline test of the generic HF adapter: local parquet, no network."""

import io
import wave
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from intelliai_datasets import hf, ingest_hf
from intelliai_datasets.ingest_hf import INDICVOICES_HI_VALID


def wav_bytes(seconds: float = 3.0, rate: int = 16000) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(rate)
        writer.writeframes(b"\x01\x00" * int(seconds * rate))
    return buffer.getvalue()


def build_shard(target: Path, rows: int = 3) -> None:
    table = pa.table(
        {
            "audio_filepath": [
                {"bytes": wav_bytes(3.0 + i), "path": f"{i}.wav"} for i in range(rows)
            ],
            "normalized": [f"नमस्ते संसार {i}" for i in range(rows)],
            "verbatim": [f"नमस्ते संसार {i}" for i in range(rows)],
            "speaker_id": [f"S{i % 2}" for i in range(rows)],
            "scenario": ["Extempore"] * rows,
            "gender": ["Female"] * rows,
            "age_group": ["18-30"] * rows,
            "district": ["Bhopal"] * rows,
        }
    )
    pq.write_table(table, target)


@pytest.fixture
def offline(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    shard = tmp_path / "shard-0.parquet"
    build_shard(shard)

    monkeypatch.setattr(hf, "discover_token", lambda: "hf_test")
    monkeypatch.setattr(hf, "dataset_revision", lambda dataset, http: "rev-test-sha")
    monkeypatch.setattr(
        hf,
        "shard_urls",
        lambda dataset, config, split, http: ["https://example.test/0.parquet"],
    )

    def fake_download(url: str, target: Path, http: object) -> None:
        target.write_bytes(shard.read_bytes())

    monkeypatch.setattr(hf, "download_shard", fake_download)
    return tmp_path


class TestOfflineIngest:
    def test_rows_become_samples_with_speakers_and_revision(self, offline: Path) -> None:
        result = ingest_hf.ingest_hf(INDICVOICES_HI_VALID, data_root=offline / "root")
        assert result.revision == "rev-test-sha"
        assert len(result.samples) == 3
        assert result.problems == ()
        speakers = {s.speaker_id for s in result.samples}
        assert speakers == {"S0", "S1"}
        first = result.samples[0]
        assert first.language == "hi"
        assert first.text.startswith("नमस्ते")
        assert "scenario='Extempore'" in first.notes
        assert (offline / "root" / first.path).exists()

    def test_ingestion_is_deterministic(self, offline: Path) -> None:
        first = ingest_hf.ingest_hf(INDICVOICES_HI_VALID, data_root=offline / "root")
        second = ingest_hf.ingest_hf(INDICVOICES_HI_VALID, data_root=offline / "root")
        assert [s.model_dump() for s in first.samples] == [s.model_dump() for s in second.samples]

    def test_bad_audio_is_a_recorded_problem_not_a_skip(
        self, offline: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        shard = tmp_path / "bad.parquet"
        table = pa.table(
            {
                "audio_filepath": [{"bytes": b"not audio at all", "path": "x.m4a"}],
                "normalized": ["पाठ"],
                "verbatim": ["पाठ"],
                "speaker_id": ["S9"],
                "scenario": ["Read"],
                "gender": ["Male"],
                "age_group": ["30-45"],
                "district": ["Indore"],
            }
        )
        pq.write_table(table, shard)

        def fake_download(url: str, target: Path, http: object) -> None:
            target.write_bytes(shard.read_bytes())

        monkeypatch.setattr(hf, "download_shard", fake_download)
        result = ingest_hf.ingest_hf(INDICVOICES_HI_VALID, data_root=offline / "root2")
        assert len(result.samples) == 0
        assert len(result.problems) == 1
        assert "RIFF" in result.problems[0]
