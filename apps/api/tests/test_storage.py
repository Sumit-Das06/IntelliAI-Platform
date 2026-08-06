"""Object storage seam: deterministic keys, fail-fast writes, kill switch.

Unit tests need no infrastructure; the round-trip test uses the real dev
MinIO and skips cleanly without it (the db_engine pattern, applied to
storage).
"""

import uuid

import pytest

from intelliai_api.core.config import CollectionSettings, Settings, StorageSettings
from intelliai_api.main import create_app
from intelliai_api.storage import (
    ObjectStorage,
    S3ObjectStorage,
    StorageWriteError,
    object_extension,
    object_key,
)

pytestmark = pytest.mark.anyio


# ── The deterministic key layout ─────────────────────────────────────────


def test_the_key_layout_is_fixed_by_design() -> None:
    key = object_key(
        organization_public_id="org_abc123",
        sample_public_id="smp_def456",
        year=2026,
        month=8,
        mime_type="audio/webm",
    )
    assert key == "speech/org_abc123/2026/08/smp_def456.webm"


def test_the_month_is_zero_padded_and_the_year_four_digits() -> None:
    key = object_key(
        organization_public_id="org_a",
        sample_public_id="smp_b",
        year=2027,
        month=1,
        mime_type="audio/wav",
    )
    assert "/2027/01/" in key


def test_extension_prefers_mime_then_filename_then_bin() -> None:
    assert object_extension("audio/mp4") == "m4a"
    assert object_extension("audio/webm;codecs=opus") == "webm"
    # Unknown MIME falls through to the uploaded filename's suffix:
    assert object_extension("application/octet-stream", "voice_note.OGG") == "ogg"
    # Nothing usable → neutral .bin, never a guess:
    assert object_extension(None, None) == "bin"
    assert object_extension("x/y", "no-extension") == "bin"
    # Hostile filename suffixes are refused, not stored into the key:
    assert object_extension(None, "clip.we$rd") == "bin"


# ── Protocol and wiring ──────────────────────────────────────────────────


class FakeObjectStorage:
    """The test double every later commit will use, proven substitutable."""

    def __init__(self) -> None:
        self.puts: list[tuple[str, bytes, str | None]] = []
        self.closed = False

    async def put(self, *, key: str, data: bytes, content_type: str | None) -> None:
        self.puts.append((key, data, content_type))

    async def close(self) -> None:
        self.closed = True


def test_the_fake_satisfies_the_protocol() -> None:
    assert isinstance(FakeObjectStorage(), ObjectStorage)
    assert isinstance(
        S3ObjectStorage(
            StorageSettings(
                _env_file=None,
                endpoint_url="http://127.0.0.1:1",
                access_key="x",
                secret_key="y",
            )
        ),
        ObjectStorage,
    )


def test_the_app_builds_the_seam_when_collection_is_enabled(settings: Settings) -> None:
    app = create_app(settings)
    assert isinstance(app.state.object_storage, S3ObjectStorage)


def test_the_kill_switch_removes_the_seam_entirely(settings: Settings) -> None:
    disabled = settings.model_copy(
        update={"collection": CollectionSettings(_env_file=None, enabled=False)}
    )
    app = create_app(disabled)
    assert app.state.object_storage is None


# ── Failure semantics: fail fast, one exception type ─────────────────────


async def test_an_unreachable_store_raises_storage_write_error_quickly() -> None:
    # 127.0.0.1:1 refuses instantly; the point pinned here is the TYPE:
    # every transport/boto failure surfaces as StorageWriteError, the one
    # exception the collection layer will catch to fail open.
    storage = S3ObjectStorage(
        StorageSettings(
            _env_file=None,
            endpoint_url="http://127.0.0.1:1",
            access_key="x",
            secret_key="y",
            audio_bucket=f"t-{uuid.uuid4().hex[:8]}",
        )
    )
    with pytest.raises(StorageWriteError):
        await storage.put(key="speech/org_x/2026/08/smp_y.webm", data=b"abc", content_type=None)
    await storage.close()


# ── Round trip against the real dev store (skips without infra) ──────────


async def test_put_round_trips_original_bytes_against_the_dev_store() -> None:
    import asyncio

    import httpx

    real = Settings()  # real env: .env locally — the db_engine pattern
    try:
        async with httpx.AsyncClient(timeout=2.0) as probe:
            await probe.get(real.storage.endpoint_url)
    except httpx.HTTPError:
        pytest.skip("requires running infrastructure (make up)")

    storage = S3ObjectStorage(real.storage)
    payload = b"RIFF....WAVEfmt original-bytes-exactly-as-received"
    key = object_key(
        organization_public_id="org_test",
        sample_public_id=f"smp_{uuid.uuid4().hex[:12]}",
        year=2026,
        month=8,
        mime_type="audio/wav",
    )
    try:
        await storage.put(key=key, data=payload, content_type="audio/wav")

        def _read_back() -> tuple[bytes, str]:
            body = storage._client.get_object(Bucket=real.storage.audio_bucket, Key=key)
            return body["Body"].read(), body.get("ContentType", "")

        stored, content_type = await asyncio.to_thread(_read_back)
        assert stored == payload  # byte-identical: no transcoding, ever
        assert content_type == "audio/wav"
        await asyncio.to_thread(
            storage._client.delete_object, Bucket=real.storage.audio_bucket, Key=key
        )
    finally:
        await storage.close()
