"""Runtime self-description: the facts only this process can honestly know.

The endpoint under test exists so a benchmark harness never *declares* a
value the runtime could have reported. These tests hold that line from
both sides: everything a record needs is present, and nothing that
changes per request has crept in beside it.
"""

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

from helpers import wav_bytes
from intelliai_runtime_contract import CONTRACT_VERSION
from intelliai_stt_runtime.api.binding import PART_FILE, PART_PARAMS, ROUTE_TRANSCRIBE
from intelliai_stt_runtime.engines.reference import BUILD, ReferenceEngine

#: Everything /info must never grow. Each belongs to monitoring, to a
#: debugger, or to an attacker's reconnaissance — none belongs in a
#: permanent benchmark record.
REFUSED_KEYS = (
    "request_count",
    "requests",
    "queue_history",
    "queue_depth",
    "log_level",
    "debug",
    "model_dir",
    "artifact_path",
    "checkpoint",
    "weights_path",
    "memory",
    "memory_mib",
    "rss",
    "cpu_percent",
    "utilization",
    "uptime_seconds",
)


def info_of(client: TestClient) -> dict[str, Any]:
    response = client.get("/info")
    assert response.status_code == 200
    document: dict[str, Any] = response.json()
    return document


def transcribe(client: TestClient, seconds: float = 0.2) -> None:
    response = client.post(
        ROUTE_TRANSCRIBE,
        files={PART_FILE: ("clip.wav", wav_bytes(duration_seconds=seconds), "audio/wav")},
        data={PART_PARAMS: json.dumps({"model": "reference"})},
    )
    assert response.status_code == 200


class TestTheLifetimeLaw:
    """`/info` reports what is true for the life of the process.

    Anything that moves per request is telemetry and belongs elsewhere.
    Without this test the rule is prose, and an endpoint governed by prose
    accumulates counters until it can no longer be quoted in evidence.
    """

    def test_info_is_identical_before_and_after_traffic(self, client: TestClient) -> None:
        before = info_of(client)
        for _ in range(25):
            transcribe(client)
        after = info_of(client)

        # The one documented exception, removed from both sides so the
        # comparison is total rather than selective.
        before_pool = before["pool"].pop("admitted")
        after_pool = after["pool"].pop("admitted")
        assert isinstance(before_pool, int) and isinstance(after_pool, int)

        assert after == before, "a field changed under traffic; /info is not lifetime-stable"

    def test_the_only_live_gauge_is_the_grandfathered_one(self, client: TestClient) -> None:
        # `pool.admitted` stays because `bench` polls it to observe
        # saturation. It is a documented debt and not a precedent: this
        # test fails the moment a second live counter is added.
        before, after = info_of(client), None
        for _ in range(10):
            transcribe(client)
        after = info_of(client)

        differing = _differing_paths(before, after)
        assert differing <= {"pool.admitted"}, f"new live fields beside the exception: {differing}"

    def test_repeated_calls_without_traffic_are_identical(self, client: TestClient) -> None:
        assert info_of(client) == info_of(client)

    def test_the_comparison_can_actually_fail(self, client: TestClient) -> None:
        """A guard on the guard.

        Under the test client every request completes before `/info` is
        called again, so `pool.admitted` returns to zero and the real
        comparison may legitimately find nothing. That makes the lifetime
        test above indistinguishable from one whose comparison is broken —
        unless the comparison is shown to detect a change it should.
        """
        document = info_of(client)
        mutated = json.loads(json.dumps(document))
        mutated["pool"]["admitted"] = document["pool"]["admitted"] + 1
        mutated["models"][0]["load_ms"] = -1.0
        mutated["environment"]["os_name"] = "somewhere else"

        assert _differing_paths(document, mutated) == {
            "pool.admitted",
            "models[0].load_ms",
            "environment.os_name",
        }

    def test_a_new_key_counts_as_a_difference(self, client: TestClient) -> None:
        document = info_of(client)
        mutated = json.loads(json.dumps(document))
        mutated["request_count"] = 7
        assert _differing_paths(document, mutated) == {"request_count"}


class TestRefusedInformation:
    """`/info` is an evidence surface, not a debugging endpoint."""

    @pytest.mark.parametrize("key", REFUSED_KEYS)
    def test_no_monitoring_or_filesystem_field_is_present(
        self, client: TestClient, key: str
    ) -> None:
        assert key not in _all_keys(info_of(client))

    def test_no_filesystem_path_leaks_anywhere_in_the_payload(self, client: TestClient) -> None:
        # Checkpoint locations are reconnaissance with no evidence value.
        rendered = json.dumps(info_of(client))
        for marker in ("/models", "\\models", "C:\\", "/home/", "/root/"):
            assert marker not in rendered


class TestPerModelSelfDescription:
    """The build and the decode configuration live with the artifact.

    Per model rather than per process: a multi-slot deployment can host
    two artifacts under different builds, and one description covering
    both would describe neither.
    """

    def test_every_model_states_its_build_and_granularity(self, client: TestClient) -> None:
        for model in info_of(client)["models"]:
            assert model["compute_type"]
            assert model["emitted_unit"] == "word"
            assert "decode_params" in model

    def test_the_reference_engine_reports_the_build_committed_evidence_uses(self) -> None:
        # Committed records cite `reference@1/deterministic`; the engine
        # now says so itself rather than an operator saying it for it.
        assert ReferenceEngine().describe().compute_type == BUILD

    def test_an_engine_with_no_decoder_reports_an_empty_map_honestly(self) -> None:
        # The one case where empty is a fact: this engine is a hash, so no
        # library default is in force. Everywhere else an empty map would
        # assert that no configuration was active when one always is.
        assert ReferenceEngine().describe().decode_params == {}

    def test_the_description_does_not_move(self, client: TestClient) -> None:
        first = info_of(client)["models"]
        for _ in range(5):
            transcribe(client)
        assert info_of(client)["models"] == first


class TestRuntimeLevelSelfDescription:
    def test_vad_ownership_is_reported(self, client: TestClient) -> None:
        # It changes what a silence probe measures: this pipeline's VAD
        # short-circuits before the engine, so the zero-hallucination
        # result is a property of the pipeline, not of the model.
        assert info_of(client)["vad_owner"] == "pipeline"

    def test_the_environment_describes_this_process(self, client: TestClient) -> None:
        environment = info_of(client)["environment"]
        for required in ("os_name", "os_release", "machine", "python_version", "interpreter"):
            assert environment[required]

    def test_hardware_class_is_null_until_the_reference_machine_is_ruled(
        self, client: TestClient
    ) -> None:
        # Present-and-null rather than absent, so a reader sees the field
        # exists and is deliberately unset. The one machine we own is
        # already spelled four ways across committed records.
        environment = info_of(client)["environment"]
        assert "hardware_class" in environment
        assert environment["hardware_class"] is None

    def test_unreadable_facts_are_omitted_rather_than_invented(self, client: TestClient) -> None:
        # Physical core count and total memory need a dependency on
        # Windows. The ruling is not to add one, and not to guess: the
        # benchmark layer records a Determination for what is absent.
        environment = info_of(client)["environment"]
        for maybe in ("cpu_physical_cores", "ram_total_mib"):
            assert maybe not in environment or isinstance(environment[maybe], int)

    def test_package_versions_are_a_declared_short_list(self, client: TestClient) -> None:
        versions = info_of(client)["environment"]["package_versions"]
        assert set(versions) <= {"faster-whisper", "ctranslate2", "numpy"}


class TestExistingConsumersAreUnaffected:
    """Additive means additive — every prior reader still works."""

    def test_the_shape_the_harness_reads_is_unchanged(self, client: TestClient) -> None:
        document = info_of(client)
        # `runner._require_hosted` and `_runtime_startup_stats`
        assert {model["artifact"] for model in document["models"]}
        for model in document["models"]:
            assert isinstance(model["load_ms"], float)
            assert isinstance(model["warmup_ms"], float)
            assert model["slot"]
        # `bench._poll_pool`
        assert set(document["pool"]) == {"admitted", "max_concurrency", "max_queue"}
        # `speech_runner` / the evaluation CLI
        assert document["service"] and document["service_version"]

    def test_contract_version_is_unchanged(self, client: TestClient) -> None:
        # Self-description is a service endpoint, not the contract. The
        # inference contract did not move, so neither did its version.
        assert info_of(client)["contract_version"] == CONTRACT_VERSION
        assert CONTRACT_VERSION == 1


def _all_keys(document: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(document, dict):
        for key, value in document.items():
            keys.add(key)
            keys |= _all_keys(value)
    elif isinstance(document, list):
        for item in document:
            keys |= _all_keys(item)
    return keys


def _differing_paths(left: Any, right: Any, prefix: str = "") -> set[str]:
    """Every dotted path whose value differs between two payloads."""
    if isinstance(left, dict) and isinstance(right, dict):
        paths: set[str] = set()
        for key in set(left) | set(right):
            here = f"{prefix}.{key}" if prefix else str(key)
            if key not in left or key not in right:
                paths.add(here)
            else:
                paths |= _differing_paths(left[key], right[key], here)
        return paths
    if isinstance(left, list) and isinstance(right, list):
        if len(left) != len(right):
            return {prefix or "<root>"}
        paths = set()
        for index, (a, b) in enumerate(zip(left, right, strict=True)):
            paths |= _differing_paths(a, b, f"{prefix}[{index}]")
        return paths
    return set() if left == right else {prefix or "<root>"}
