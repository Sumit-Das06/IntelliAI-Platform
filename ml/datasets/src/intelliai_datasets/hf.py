"""Hugging Face access shared by every dataset adapter.

Token discovery follows the standard HF conventions — the ``HF_TOKEN``
environment variable, then the ``huggingface-cli``-style token file —
and the token is HANDLED, never surfaced: it is read into a client
header and appears in no log, no report, no manifest, no exception
message. Gated sources ingest exactly like open ones once the founder
has accepted their terms; a missing token is a detected, reported
condition, never a faked download.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import httpx

_TOKEN_FILE = Path.home() / ".cache" / "huggingface" / "token"
_API = "https://huggingface.co/api/datasets"
_DOWNLOAD_TIMEOUT = httpx.Timeout(600.0, connect=30.0)
_DOWNLOAD_ATTEMPTS = 4


class HfAccessError(RuntimeError):
    """Access is missing or refused; the message never contains the token."""


def discover_token() -> str | None:
    """Locate a token without ever printing it."""
    for env in ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN"):
        value = os.environ.get(env, "").strip()
        if value:
            return value
    if _TOKEN_FILE.exists():
        value = _TOKEN_FILE.read_text(encoding="utf-8").strip()
        if value:
            return value
    return None


def client(token: str | None) -> httpx.Client:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return httpx.Client(follow_redirects=True, timeout=_DOWNLOAD_TIMEOUT, headers=headers)


def dataset_revision(dataset: str, http: httpx.Client) -> str:
    """The dataset repo's current commit sha — pinned into provenance."""
    response = http.get(f"{_API}/{dataset}")
    if response.status_code in (401, 403):
        msg = f"dataset {dataset}: access refused (missing/insufficient token or unaccepted terms)"
        raise HfAccessError(msg)
    response.raise_for_status()
    sha = response.json().get("sha")
    if not isinstance(sha, str) or not sha:
        msg = f"dataset {dataset}: no revision sha in API response"
        raise HfAccessError(msg)
    return sha


def shard_urls(dataset: str, config: str, split: str, http: httpx.Client) -> list[str]:
    response = http.get(f"{_API}/{dataset}/parquet/{config}/{split}")
    if response.status_code in (401, 403):
        msg = (
            f"dataset {dataset}: parquet listing refused for {config}/{split} "
            "(missing/insufficient token or unaccepted terms)"
        )
        raise HfAccessError(msg)
    response.raise_for_status()
    urls = json.loads(response.content)
    if not isinstance(urls, list) or not all(isinstance(u, str) for u in urls):
        msg = f"dataset {dataset}: unexpected parquet index shape for {config}/{split}"
        raise HfAccessError(msg)
    return sorted(urls)


def download_shard(url: str, target: Path, http: httpx.Client) -> None:
    """Stream to a temp file with retries; atomic rename on success."""
    partial = target.with_suffix(target.suffix + ".partial")
    last_error: Exception | None = None
    for attempt in range(1, _DOWNLOAD_ATTEMPTS + 1):
        try:
            with http.stream("GET", url) as response:
                response.raise_for_status()
                with partial.open("wb") as handle:
                    for chunk in response.iter_bytes(1 << 20):
                        handle.write(chunk)
            partial.replace(target)
            return
        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            last_error = exc
            partial.unlink(missing_ok=True)
            if attempt < _DOWNLOAD_ATTEMPTS:
                time.sleep(2.0 * attempt)
    msg = f"shard download failed after {_DOWNLOAD_ATTEMPTS} attempts: {url}"
    raise HfAccessError(msg) from last_error
