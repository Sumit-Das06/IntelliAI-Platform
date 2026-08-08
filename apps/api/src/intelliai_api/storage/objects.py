"""Object storage for collected speech samples — the S3 seam.

Charter: this package owns the generic-S3 abstraction and nothing else.
No business rules (who may store lives in the collection service), no
schema knowledge, no HTTP shapes. Generic S3 API only, per ADR-0011: the
dev endpoint is MinIO, production is any managed S3 — application code
must never know which.

Two laws from the approved design:

- **Fail fast** so callers can fail OPEN: hard connect/read timeouts and
  no retries. A degraded store must cost a bounded few seconds, never a
  hang — that bound is what makes "storage failure never fails the
  customer request" a safe promise for the caller to make.
- **Original bytes exactly as received.** No transcoding, no
  normalisation before storage. The runtime may convert for inference;
  the dataset preserves what the user's device produced, so today's
  pipeline choices never fossilize into tomorrow's training data.
"""

import asyncio
from typing import TYPE_CHECKING, Protocol, runtime_checkable

import structlog

from intelliai_api.core.config import StorageSettings

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client

logger = structlog.get_logger("intelliai_api.storage")

#: Extension by MIME type for the deterministic key layout. Closed map
#: with a neutral fallback: an unknown container is stored as .bin rather
#: than guessed — the mime_type column keeps the truth either way.
_EXTENSIONS = {
    "audio/webm": "webm",
    "video/webm": "webm",
    "audio/ogg": "ogg",
    "application/ogg": "ogg",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/wave": "wav",
    "audio/flac": "flac",
    "audio/x-flac": "flac",
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/mp4": "m4a",
    "audio/x-m4a": "m4a",
    "audio/m4a": "m4a",
    "audio/aac": "aac",
    "video/mp4": "mp4",
}


def object_extension(mime_type: str | None, filename: str | None = None) -> str:
    """The stored object's extension: MIME first, filename second, .bin last."""
    if mime_type:
        bare = mime_type.split(";", 1)[0].strip().lower()
        if bare in _EXTENSIONS:
            return _EXTENSIONS[bare]
    if filename and "." in filename:
        candidate = filename.rsplit(".", 1)[1].strip().lower()
        if candidate.isalnum() and 1 <= len(candidate) <= 8:
            return candidate
    return "bin"


def object_key(
    *,
    organization_public_id: str,
    sample_public_id: str,
    year: int,
    month: int,
    mime_type: str | None,
    filename: str | None = None,
) -> str:
    """The deterministic key layout, fixed by design:

    ``speech/{org_public_id}/{YYYY}/{MM}/{sample_public_id}.{ext}``

    Capability-prefixed so future sample types (ocr/, translation/, ...)
    are siblings in the same bucket; org-prefixed so tenant-wide listing
    and deletion are prefix operations; month-partitioned so no directory
    grows unbounded. Pure function — the caller supplies the clock.
    """
    extension = object_extension(mime_type, filename)
    return f"speech/{organization_public_id}/{year:04d}/{month:02d}/{sample_public_id}.{extension}"


class StorageWriteError(Exception):
    """A write did not durably complete. The caller decides what that
    means — for collection it means: log, skip, never fail the request."""


class StorageReadError(Exception):
    """A read did not complete. Unlike writes, reads serve a customer who
    asked for exactly this object — the caller maps this to its contract."""


class StorageObjectMissingError(StorageReadError):
    """The key does not exist — a row without its object. For the audio
    endpoint that is a 404; for operators it is a data-integrity signal."""


@runtime_checkable
class ObjectStorage(Protocol):
    """What the platform needs from an object store: durable puts, reads
    for the console's playback, existence probes for dataset preparation,
    and a clean shutdown. This protocol grew ``get`` when the Speech
    Samples page needed it and ``head`` when training-data validation
    needed to check a thousand objects without downloading a thousand
    audio files — never speculatively."""

    async def put(self, *, key: str, data: bytes, content_type: str | None) -> None: ...

    async def get(self, *, key: str) -> bytes: ...

    async def head(self, *, key: str) -> None: ...

    async def close(self) -> None: ...


class S3ObjectStorage:
    """boto3 against any S3-compatible endpoint, offloaded to threads.

    boto3 is synchronous; every call runs in ``asyncio.to_thread`` so the
    event loop never blocks on storage I/O. One PUT per consented request
    is nowhere near thread-pool pressure (in-flight requests are capped
    far below the default executor's size by the connection pool).
    """

    def __init__(self, settings: StorageSettings) -> None:
        # Imported here, not at module top: boto3 costs real import time
        # and only the serving process ever needs it — the CLI and most
        # tests should not pay for it.
        import boto3
        from botocore.config import Config

        self._bucket = settings.audio_bucket
        self._client: S3Client = boto3.client(
            "s3",
            endpoint_url=settings.endpoint_url,
            aws_access_key_id=settings.access_key,
            aws_secret_access_key=settings.secret_key.get_secret_value(),
            region_name=settings.region,
            # Fail fast is what makes fail-open survivable: a dead store
            # costs at most ~7s once, never a hang, and the collection
            # layer treats that as "skip", never as "fail the request".
            config=Config(
                connect_timeout=2,
                read_timeout=5,
                retries={"max_attempts": 1},
            ),
        )
        self._bucket_ensured = False
        self._ensure_lock = asyncio.Lock()

    async def put(self, *, key: str, data: bytes, content_type: str | None) -> None:
        try:
            await self._ensure_bucket()
            await asyncio.to_thread(
                self._client.put_object,
                Bucket=self._bucket,
                Key=key,
                Body=data,
                ContentType=content_type or "application/octet-stream",
            )
        except StorageWriteError:
            raise
        except Exception as exc:
            raise StorageWriteError(f"put {key!r} failed: {type(exc).__name__}") from exc

    async def get(self, *, key: str) -> bytes:
        try:
            response = await asyncio.to_thread(
                self._client.get_object, Bucket=self._bucket, Key=key
            )
            return await asyncio.to_thread(response["Body"].read)
        except self._client.exceptions.NoSuchKey as exc:
            raise StorageObjectMissingError(f"object {key!r} does not exist") from exc
        except StorageReadError:
            raise
        except Exception as exc:
            raise StorageReadError(f"get {key!r} failed: {type(exc).__name__}") from exc

    async def head(self, *, key: str) -> None:
        """Existence probe: returns silently when the object is there.

        HEAD has no body, so S3 reports absence as a bare 404 ClientError
        rather than ``NoSuchKey`` — mapped here to the same
        ``StorageObjectMissingError`` the read path raises, so callers
        distinguish "definitively absent" (a validation finding) from
        "store unreachable" (an operational failure) by type alone.
        """
        from botocore.exceptions import ClientError

        try:
            await asyncio.to_thread(self._client.head_object, Bucket=self._bucket, Key=key)
        except ClientError as exc:
            status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            if status == 404:
                raise StorageObjectMissingError(f"object {key!r} does not exist") from exc
            raise StorageReadError(f"head {key!r} failed: {type(exc).__name__}") from exc
        except Exception as exc:
            raise StorageReadError(f"head {key!r} failed: {type(exc).__name__}") from exc

    async def _ensure_bucket(self) -> None:
        """Create the bucket on first write if absent (dev MinIO has no
        provisioning step); once per process. Production buckets exist
        already, so this is a single fast HEAD there."""
        if self._bucket_ensured:
            return
        async with self._ensure_lock:
            if self._bucket_ensured:
                return
            try:
                await asyncio.to_thread(self._client.head_bucket, Bucket=self._bucket)
            except Exception:
                await asyncio.to_thread(self._client.create_bucket, Bucket=self._bucket)
                logger.info("storage.bucket_created", bucket=self._bucket)
            self._bucket_ensured = True

    async def close(self) -> None:
        await asyncio.to_thread(self._client.close)
