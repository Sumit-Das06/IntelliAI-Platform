"""ArtifactStore: hash-verified model files, downloaded once, trusted never.

Every artifact file is pinned by SHA-256 in code (the same discipline as
the evaluation dataset manifests). `ensure()` makes the artifact locally
present AND verified: cached files are re-hashed on every startup — a
tampered or corrupted cache is treated exactly like a bad download. Writes
are atomic (temp file + rename), so a crashed download can never
masquerade as a complete artifact. Weights never enter git (large-file
guard); the store directory is gitignored.

Verification failures are ``internal``, not ``invalid_input``: a checksum
mismatch is a supply-chain or deployment problem, never the customer's.
"""

import hashlib
import shutil
from dataclasses import dataclass
from pathlib import Path

import httpx
import structlog

from intelliai_runtime_contract import RuntimeErrorType
from intelliai_stt_runtime.failures import RuntimeServiceError

logger = structlog.get_logger(__name__)

_CHUNK_BYTES = 1024 * 1024


@dataclass(frozen=True)
class ArtifactFile:
    """One pinned file of an artifact version."""

    filename: str
    url: str
    sha256: str


@dataclass(frozen=True)
class ArtifactSpec:
    """Everything needed to make an artifact version locally real."""

    artifact: str  # registry artifact identifier, e.g. "whisper-small"
    version: int
    files: tuple[ArtifactFile, ...]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


class ArtifactStore:
    """Owns the model cache directory: layout, downloads, verification."""

    def __init__(self, root: Path, client: httpx.Client | None = None) -> None:
        self._root = root
        self._client = client

    def artifact_dir(self, spec: ArtifactSpec) -> Path:
        return self._root / spec.artifact / f"v{spec.version}"

    def ensure(self, spec: ArtifactSpec) -> Path:
        """Return the artifact's local directory, downloading and verifying
        as needed. Every file is hash-checked on every call — nothing is
        loaded on trust."""
        target = self.artifact_dir(spec)
        target.mkdir(parents=True, exist_ok=True)
        for file in spec.files:
            path = target / file.filename
            if path.exists():
                if sha256_file(path) == file.sha256:
                    continue
                logger.info("artifact_cache_invalid", artifact=spec.artifact, file=file.filename)
                path.unlink()
            self._download(spec, file, path)
        logger.info("artifact_verified", artifact=spec.artifact, version=spec.version)
        return target

    def _download(self, spec: ArtifactSpec, file: ArtifactFile, path: Path) -> None:
        logger.info("artifact_download_started", artifact=spec.artifact, file=file.filename)
        partial = path.with_suffix(path.suffix + ".partial")
        digest = hashlib.sha256()
        client = self._client or httpx.Client(follow_redirects=True, timeout=120)
        owns_client = self._client is None
        try:
            with client.stream("GET", file.url) as response:
                response.raise_for_status()
                with partial.open("wb") as handle:
                    for chunk in response.iter_bytes(_CHUNK_BYTES):
                        digest.update(chunk)
                        handle.write(chunk)
        except httpx.HTTPError as exc:
            partial.unlink(missing_ok=True)
            raise RuntimeServiceError(
                RuntimeErrorType.INTERNAL,
                f"artifact download failed for {spec.artifact}/{file.filename}",
            ) from exc
        finally:
            if owns_client:
                client.close()
        if digest.hexdigest() != file.sha256:
            partial.unlink(missing_ok=True)
            raise RuntimeServiceError(
                RuntimeErrorType.INTERNAL,
                f"artifact checksum mismatch for {spec.artifact}/{file.filename}; "
                "refusing to load unverified weights",
            )
        shutil.move(partial, path)
        logger.info("artifact_download_verified", artifact=spec.artifact, file=file.filename)
