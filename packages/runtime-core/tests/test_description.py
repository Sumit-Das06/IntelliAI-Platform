"""Self-description: read the library's defaults, never restate them."""

import os
import platform

from intelliai_runtime_core import (
    EngineDescription,
    effective_parameters,
    host_environment,
    interpreter_identity,
    package_versions,
)


class TestEffectiveParameters:
    """A decode map must describe the system, not the two lines we wrote."""

    def test_library_defaults_are_reported_even_though_nobody_passed_them(self) -> None:
        # This is the whole point. A beam search and a temperature ladder
        # were in force on every measurement we have ever taken, from the
        # library's own signature. An empty map would have asserted that
        # no decode configuration was active.
        defaults = {"beam_size": 5, "temperature": [0.0, 0.2], "task": "translate"}
        assert effective_parameters(defaults, ("beam_size", "temperature"), {}) == {
            "beam_size": "5",
            "temperature": "0.0,0.2",
        }

    def test_an_explicit_override_wins_over_the_default(self) -> None:
        defaults = {"task": "translate", "vad_filter": True}
        overlaid = effective_parameters(
            defaults, ("task", "vad_filter"), {"task": "transcribe", "vad_filter": False}
        )
        assert overlaid == {"task": "transcribe", "vad_filter": "false"}

    def test_a_changed_library_default_changes_the_report(self) -> None:
        # The reason this is read rather than hard-coded: a dependency
        # upgrade changes the measured system, and a constant would keep
        # reporting the old value with no diff anywhere in the repository.
        wanted = ("beam_size",)
        assert effective_parameters({"beam_size": 5}, wanted, {}) == {"beam_size": "5"}
        assert effective_parameters({"beam_size": 1}, wanted, {}) == {"beam_size": "1"}

    def test_parameters_nobody_asked_for_are_not_reported(self) -> None:
        # `/info` is an evidence surface. A full signature dump would make
        # it a debugging endpoint by accretion.
        defaults = {"beam_size": 5, "chunk_length": 30, "hotwords": None}
        assert set(effective_parameters(defaults, ("beam_size",), {})) == {"beam_size"}

    def test_a_per_request_parameter_is_simply_never_wanted(self) -> None:
        # `language` varies per request, and this endpoint reports only
        # what is true for the process's lifetime.
        defaults = {"language": None, "beam_size": 5}
        assert "language" not in effective_parameters(defaults, ("beam_size",), {})

    def test_booleans_render_unambiguously(self) -> None:
        # `bool` is an `int` subclass; rendering it as 1/0 would make a
        # flag indistinguishable from a count in committed evidence.
        assert effective_parameters({"a": True, "b": False}, ("a", "b"), {}) == {
            "a": "true",
            "b": "false",
        }

    def test_a_missing_parameter_is_omitted_rather_than_guessed(self) -> None:
        assert effective_parameters({}, ("beam_size",), {}) == {}


class TestEngineDescription:
    def test_it_serialises_flat_for_the_info_payload(self) -> None:
        described = EngineDescription(
            compute_type="int8", emitted_unit="word", decode_params={"beam_size": "5"}
        )
        assert described.as_dict() == {
            "compute_type": "int8",
            "emitted_unit": "word",
            "decode_params": {"beam_size": "5"},
        }

    def test_an_engine_with_no_decoder_carries_an_empty_map(self) -> None:
        assert (
            EngineDescription(compute_type="deterministic", emitted_unit="word").decode_params == {}
        )


class TestHostEnvironment:
    """Facts, never classifications — and never a fabricated value."""

    def test_it_reports_what_this_process_can_read(self) -> None:
        environment = host_environment()
        assert environment["os_name"] == platform.system()
        assert environment["machine"] == platform.machine()
        assert environment["python_version"] == platform.python_version()

    def test_it_never_classifies_the_host(self) -> None:
        # Whether this is "bare metal" or "a VM", and which hardware era
        # it belongs to, are judgements. This module reports os_release
        # and lets the reader decide; inventing the label would put a
        # guess in a permanent record dressed as a measurement.
        environment = host_environment()
        assert "virtualisation" not in environment
        assert "power_profile" not in environment

    def test_hardware_class_is_present_and_null(self) -> None:
        # Present so a reader sees the field exists and is deliberately
        # unset, pending ratification of the reference machine.
        environment = host_environment()
        assert "hardware_class" in environment
        assert environment["hardware_class"] is None

    def test_thread_variables_are_read_from_this_process(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        # The only place the question has a true answer: a harness reading
        # its OWN environment learns nothing about the runtime's pool.
        monkeypatch.setenv("OMP_NUM_THREADS", "4")
        assert host_environment()["thread_env"]["OMP_NUM_THREADS"] == "4"

    def test_unset_thread_variables_are_omitted_not_defaulted(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        # An unset variable means the library defaulted internally, which
        # is not the same as "one thread" and must not be recorded as it.
        for name in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
            monkeypatch.delenv(name, raising=False)
        assert "OMP_NUM_THREADS" not in host_environment().get("thread_env", {})

    def test_it_is_stable_across_calls(self) -> None:
        # It feeds a lifetime-stable endpoint; anything varying here would
        # break that guarantee at the source.
        assert host_environment() == host_environment()

    def test_no_optional_dependency_is_required(self) -> None:
        # Standard library only, by ruling. `host_environment()` running
        # at all in this suite is the proof: the runtime-core package
        # declares no introspection dependency.
        assert host_environment()["os_name"]
        assert os.cpu_count() is None or "cpu_logical_threads" in host_environment()


class TestPackageVersions:
    def test_only_declared_packages_are_reported(self) -> None:
        assert set(package_versions(("pydantic",))) <= {"pydantic"}

    def test_an_absent_optional_extra_is_skipped_rather_than_erroring(self) -> None:
        # Engine extras are absent in CI by design; asking for one must
        # not take down `/info`.
        assert package_versions(("definitely-not-installed-xyz",)) == {}


def test_interpreter_identity_is_one_line() -> None:
    # It goes into a JSON record; an embedded newline makes a committed
    # payload awkward to diff for no benefit.
    assert "\n" not in interpreter_identity()
