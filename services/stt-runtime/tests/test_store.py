"""ArtifactStore: nothing is ever loaded on trust."""

import hashlib
from pathlib import Path

import httpx
import pytest

from intelliai_runtime_contract import RuntimeErrorType
from intelliai_stt_runtime.failures import RuntimeServiceError
from intelliai_stt_runtime.manager import ArtifactFile, ArtifactSpec, ArtifactStore

PAYLOAD = b"deterministic model weights " * 100
GOOD_SHA = hashlib.sha256(PAYLOAD).hexdigest()


def spec(sha256: str = GOOD_SHA) -> ArtifactSpec:
    return ArtifactSpec(
        artifact="test-artifact",
        version=1,
        files=(
            ArtifactFile(
                filename="model.bin", url="https://weights.example/model.bin", sha256=sha256
            ),
        ),
    )


class CountingTransport(httpx.BaseTransport):
    def __init__(self, payload: bytes = PAYLOAD, status: int = 200) -> None:
        self.requests = 0
        self._payload = payload
        self._status = status

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        self.requests += 1
        return httpx.Response(self._status, content=self._payload)


def make_store(tmp_path: Path, transport: CountingTransport) -> ArtifactStore:
    return ArtifactStore(tmp_path, client=httpx.Client(transport=transport))


class TestEnsure:
    def test_downloads_verifies_and_caches(self, tmp_path: Path) -> None:
        transport = CountingTransport()
        store = make_store(tmp_path, transport)
        target = store.ensure(spec())
        assert (target / "model.bin").read_bytes() == PAYLOAD
        assert transport.requests == 1
        # Second ensure: hash-verified cache hit, no network.
        store.ensure(spec())
        assert transport.requests == 1

    def test_checksum_mismatch_refuses_and_leaves_nothing(self, tmp_path: Path) -> None:
        transport = CountingTransport()
        store = make_store(tmp_path, transport)
        bad = spec(sha256="0" * 64)
        with pytest.raises(RuntimeServiceError, match="checksum") as exc_info:
            store.ensure(bad)
        assert exc_info.value.error_type is RuntimeErrorType.INTERNAL
        target = store.artifact_dir(bad)
        assert not list(target.glob("*.bin"))
        assert not list(target.glob("*.partial"))

    def test_corrupted_cache_is_redownloaded(self, tmp_path: Path) -> None:
        transport = CountingTransport()
        store = make_store(tmp_path, transport)
        target = store.ensure(spec())
        (target / "model.bin").write_bytes(b"tampered")
        store.ensure(spec())  # re-verifies, detects, re-downloads
        assert (target / "model.bin").read_bytes() == PAYLOAD
        assert transport.requests == 2

    def test_download_failure_is_internal(self, tmp_path: Path) -> None:
        store = make_store(tmp_path, CountingTransport(status=503))
        with pytest.raises(RuntimeServiceError, match="download") as exc_info:
            store.ensure(spec())
        assert exc_info.value.error_type is RuntimeErrorType.INTERNAL

    def test_layout_is_artifact_slash_version(self, tmp_path: Path) -> None:
        store = make_store(tmp_path, CountingTransport())
        assert store.ensure(spec()) == tmp_path / "test-artifact" / "v1"
