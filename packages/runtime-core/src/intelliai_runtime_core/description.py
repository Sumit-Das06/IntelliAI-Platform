"""Runtime self-description: the facts only the serving process knows.

A benchmark harness measures a runtime over HTTP, from another process and
often another container. Three kinds of fact are invisible from there and
decisive for what a measurement means: which build of the artifact is
loaded, what decode configuration it runs under, and what the host is.

Without this module the harness has two options, both bad. It can take a
flag — *"a hand-typed value that the system already knows is a
transcription error waiting to be committed"* — or it can leave the field
empty, which asserts that no configuration was active when one always is.

**Why the runtime is authoritative, and not merely convenient.** This is
arithmetic, not preference. ``OMP_NUM_THREADS`` read from the harness is
the *harness's* variable. ``os.cpu_count()`` inside a container reflects
that container. Our own committed evidence already spans both cases on one
physical machine — quality records taken natively, the production ladder
under Docker/WSL2 — so only the process being measured can answer
questions about the process being measured.

**Facts, never classifications.** This module reports what it can read and
stops. It does not decide whether the host is "bare metal" or "a VM", and
it does not label a hardware era: those are judgements, made by the
benchmark layer or by a human, from the facts below. Inventing them here
would put a guess in a permanent record wearing the clothes of a
measurement.

**Absence is omission, never a fabricated value.** A fact this process
cannot read with the standard library is simply not reported. The
benchmark layer turns that silence into an explicit Determination. There
is no dependency here that exists to make the block look complete.
"""

from __future__ import annotations

import os
import platform
import sys
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from importlib import metadata
from typing import Any, Final

#: Thread-pool variables worth recording, in the order a reader expects.
#: CPU recognition throughput is strongly thread-sensitive, so a CPU
#: benchmark without a recorded thread configuration is not reproducible.
#: Read from THIS process's environment, which is the only place the
#: question has a true answer.
_THREAD_VARIABLES: Final = (
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
)


@dataclass(frozen=True)
class EngineDescription:
    """How one loaded engine is configured to decode.

    Per artifact, not per process: a multi-slot runtime can host two
    artifacts under different builds, and a description that averaged them
    would describe neither.
    """

    #: The build — precision, quantization, anything deterministic applied
    #: at load. Quality binds to (artifact, build) and never to artifact
    #: alone: an int8 build is the same identity and not necessarily the
    #: same behaviour.
    compute_type: str
    #: What this engine emits: word | character | byte. Recorded so a
    #: reader can interpret a character-emitting model's word error rate.
    #: It never selects a metric — primacy is fixed per language and
    #: corpus version, never per candidate.
    emitted_unit: str
    #: The decode configuration **actually in force**, library defaults
    #: included. An empty map means this engine has no decoder at all, not
    #: that nobody looked. Per-request parameters (language, the audio
    #: itself) are excluded: this endpoint reports what is true for the
    #: process's lifetime.
    decode_params: Mapping[str, str] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "compute_type": self.compute_type,
            "emitted_unit": self.emitted_unit,
            "decode_params": dict(self.decode_params),
        }


def effective_parameters(
    signature_defaults: Mapping[str, Any],
    wanted: Iterable[str],
    overrides: Mapping[str, Any],
) -> dict[str, str]:
    """The configuration a call will really run under.

    Built from the *library's own* defaults overlaid with what the adapter
    explicitly passes, rather than from a hand-maintained list of
    constants. That is the whole point: a dependency upgrade that changes
    a default changes the measured system, and a constant would keep
    reporting the old value with no diff anywhere in this repository.

    Values are stringified because a decode map is read, compared and
    stored as evidence — not arithmetic — and a float that round-trips
    differently through JSON would make two identical configurations look
    like two.
    """
    effective: dict[str, str] = {}
    for name in wanted:
        if name in overrides:
            effective[name] = _render(overrides[name])
        elif name in signature_defaults:
            effective[name] = _render(signature_defaults[name])
    return effective


def _render(value: Any) -> str:
    if isinstance(value, bool):  # before int: bool is an int subclass
        return "true" if value else "false"
    if isinstance(value, (list, tuple)):
        return ",".join(_render(item) for item in value)
    return str(value)


def host_environment() -> dict[str, Any]:
    """What this process can honestly say about the machine it runs on.

    Standard library only, by ruling: a dependency added to make the block
    look complete would be a dependency added to make a record look
    complete. Anything unreadable is omitted, and the benchmark layer
    records a Determination for it — physical core count and total memory
    are the usual casualties on Windows.
    """
    environment: dict[str, Any] = {
        "os_name": platform.system(),
        "os_release": platform.release(),
        "os_version": platform.version(),
        "machine": platform.machine(),
        "python_version": platform.python_version(),
    }

    # `platform.processor()` is empty on several Linux builds; report it
    # only when the machine actually answered.
    processor = platform.processor()
    if processor:
        environment["cpu_model"] = processor

    logical = os.cpu_count()
    if logical is not None:
        environment["cpu_logical_threads"] = logical

    # POSIX only. Absent on Windows without ctypes, and a nice-to-have is
    # not worth a platform-specific pointer cast that has already produced
    # one silent zero in this project's history.
    total = _total_memory_mib()
    if total is not None:
        environment["ram_total_mib"] = total

    threads = {name: os.environ[name] for name in _THREAD_VARIABLES if name in os.environ}
    if threads:
        environment["thread_env"] = threads

    #: The era label a comparability check blocks on. Reported as null
    #: rather than omitted, so a reader can see the field exists and is
    #: deliberately unset: the reference machine has not been ratified,
    #: and it is already spelled four ways across committed records.
    environment["hardware_class"] = None
    return environment


def package_versions(names: Iterable[str]) -> dict[str, str]:
    """Installed versions of the packages a runtime's engines depend on.

    A declared, short list rather than everything importable. `/info` is
    an evidence surface, and a full dependency dump would make it a
    debugging endpoint by accretion.
    """
    found: dict[str, str] = {}
    for name in names:
        try:
            found[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            continue  # an engine extra that is simply not installed here
    return found


def _total_memory_mib() -> int | None:
    """POSIX only, and deliberately not worked around on Windows.

    The alternative is a ctypes pointer cast into a platform API, which
    has already produced one silent zero in this project's history. A
    number that is quietly wrong is worse than a field the benchmark layer
    records an explicit Determination for.
    """
    sysconf = getattr(os, "sysconf", None)  # absent on Windows
    if sysconf is None:
        return None
    try:
        pages = int(sysconf("SC_PHYS_PAGES"))
        page_size = int(sysconf("SC_PAGE_SIZE"))
    except (ValueError, OSError):
        return None
    if pages < 0 or page_size < 0:
        return None
    return int(pages * page_size / (1024 * 1024))


def interpreter_identity() -> str:
    """The exact interpreter, for the record. Version alone is not enough
    when a build flag can change numeric behaviour."""
    return sys.version.replace("\n", " ")
