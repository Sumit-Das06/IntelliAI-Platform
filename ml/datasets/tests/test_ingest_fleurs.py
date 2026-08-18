"""FLEURS ingestion: config mapping and resumable shard downloads."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from intelliai_datasets.ingest_fleurs import (
    LANGUAGE_BY_CONFIG,
    FleursIngestError,
    _download_shard,
    ingest_fleurs,
)


class TestLanguageMapping:
    def test_the_approved_configs_are_mapped(self) -> None:
        # hi_in/cmn: the original eval sources; en_us: the M23 English
        # retention slice (the one approved OPEN English source).
        assert LANGUAGE_BY_CONFIG["hi_in"] == "hi"
        assert LANGUAGE_BY_CONFIG["cmn_hans_cn"] == "zh"
        assert LANGUAGE_BY_CONFIG["en_us"] == "en"

    def test_an_unmapped_config_is_refused_loudly(self, tmp_path: Path) -> None:
        with pytest.raises(FleursIngestError, match="unmapped FLEURS config"):
            ingest_fleurs(config="xx_yy", split="train", data_root=tmp_path)


class TestResumableDownload:
    """M23: a retry RESUMES the partial with a Range request."""

    def test_a_partial_resumes_with_a_range_request(self, tmp_path: Path) -> None:
        target = tmp_path / "0.parquet"
        target.with_suffix(".parquet.partial").write_bytes(b"abc")
        seen_ranges: list[str | None] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen_ranges.append(request.headers.get("Range"))
            assert request.headers["Range"] == "bytes=3-"
            return httpx.Response(206, content=b"def")

        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            _download_shard("https://host/0.parquet", target, client)
        assert target.read_bytes() == b"abcdef"
        assert seen_ranges == ["bytes=3-"]

    def test_a_200_despite_the_range_starts_the_bytes_over(self, tmp_path: Path) -> None:
        # A server free to ignore Range must not produce duplicated bytes.
        target = tmp_path / "0.parquet"
        target.with_suffix(".parquet.partial").write_bytes(b"abc")

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=b"xyzxyz")

        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            _download_shard("https://host/0.parquet", target, client)
        assert target.read_bytes() == b"xyzxyz"

    def test_a_fresh_download_sends_no_range(self, tmp_path: Path) -> None:
        target = tmp_path / "0.parquet"

        def handler(request: httpx.Request) -> httpx.Response:
            assert "Range" not in request.headers
            return httpx.Response(200, content=b"bytes")

        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            _download_shard("https://host/0.parquet", target, client)
        assert target.read_bytes() == b"bytes"
        assert not target.with_suffix(".parquet.partial").exists()

    def test_forward_progress_resets_the_attempt_budget(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A pipe dropping every MiB still finishes an 8 MiB "shard"
        # (7 drops > the 6-attempt budget) because each drop banks
        # bytes; only consecutive ZERO-progress failures count.
        import intelliai_datasets.ingest_fleurs as module

        monkeypatch.setattr(module.time, "sleep", lambda _: None)
        target = tmp_path / "0.parquet"
        step = 1 << 20  # the downloader's iter_bytes chunk size
        total = bytes(8 * step)

        def dropping(chunk: bytes):  # type: ignore[no-untyped-def]
            yield chunk
            raise httpx.TransportError("simulated mid-stream drop")

        def handler(request: httpx.Request) -> httpx.Response:
            start = 0
            if "Range" in request.headers:
                start = int(request.headers["Range"].split("=")[1].rstrip("-"))
            status = 206 if start else 200
            remaining = total[start:]
            if len(remaining) <= step:
                return httpx.Response(status, content=remaining)
            return httpx.Response(status, content=dropping(remaining[:step]))

        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            _download_shard("https://host/0.parquet", target, client)
        assert target.read_bytes() == total

    def test_consecutive_zero_progress_failures_still_bound_the_loop(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import intelliai_datasets.ingest_fleurs as module

        monkeypatch.setattr(module.time, "sleep", lambda _: None)
        calls = {"n": 0}

        def handler(_request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            raise httpx.ConnectError("no route")

        with (
            httpx.Client(transport=httpx.MockTransport(handler)) as client,
            pytest.raises(FleursIngestError, match="stalled attempts"),
        ):
            _download_shard("https://host/0.parquet", tmp_path / "0.parquet", client)
        assert calls["n"] == 6
