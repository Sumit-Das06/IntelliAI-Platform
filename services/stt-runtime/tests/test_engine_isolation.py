"""CI-enforced boundaries (M2 refinement 10, ADR-0016).

Rule 1: only engines/ modules may import foundation-model libraries.
Rule 2: engines/ must not import transport (engines are pure adapters).
Rule 3: the service's own dependency list carries no foundation-model
        library — engine libraries arrive as engine-owned extras (step 5).

Static AST analysis, so the rules hold for every module — including ones
added after this test was written. Adding a new engine library to the
denylist is part of adding the engine.
"""

import ast
import tomllib
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]
SRC = SERVICE_ROOT / "src" / "intelliai_stt_runtime"

FOUNDATION_MODEL_LIBS = {
    "faster_whisper",
    "ctranslate2",
    "whisper",
    "torch",
    "torchaudio",
    "tensorflow",
    "transformers",
    "onnxruntime",
    "openvino",
    "vllm",
    "librosa",
    "soundfile",
}

TRANSPORT_LIBS = {"fastapi", "starlette", "uvicorn", "httpx", "requests", "aiohttp"}


def import_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.add(node.module.split(".")[0])
    return roots


def modules() -> list[Path]:
    found = sorted(SRC.rglob("*.py"))
    assert found, f"no modules found under {SRC}"
    return found


def test_only_engines_may_import_foundation_model_libraries() -> None:
    for module in modules():
        if "engines" in module.relative_to(SRC).parts:
            continue
        offending = import_roots(module) & FOUNDATION_MODEL_LIBS
        assert not offending, (
            f"{module.relative_to(SERVICE_ROOT)} imports foundation-model "
            f"libraries {sorted(offending)} — only engines/ may (ADR-0016)"
        )


def test_engines_never_import_transport() -> None:
    engine_modules = [m for m in modules() if "engines" in m.relative_to(SRC).parts]
    assert engine_modules
    for module in engine_modules:
        offending = import_roots(module) & TRANSPORT_LIBS
        assert not offending, (
            f"{module.relative_to(SERVICE_ROOT)} imports transport "
            f"{sorted(offending)} — engines are pure adapters"
        )


def test_engines_never_import_the_http_binding() -> None:
    for module in modules():
        if "engines" not in module.relative_to(SRC).parts:
            continue
        tree = ast.parse(module.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.startswith("intelliai_stt_runtime.api"), (
                    f"{module.relative_to(SERVICE_ROOT)} imports the api layer"
                )


def test_service_dependencies_are_provider_independent() -> None:
    with (SERVICE_ROOT / "pyproject.toml").open("rb") as handle:
        pyproject = tomllib.load(handle)
    dependencies = " ".join(pyproject["project"]["dependencies"]).lower()
    for lib in FOUNDATION_MODEL_LIBS:
        assert lib.replace("_", "-") not in dependencies, (
            f"foundation-model library {lib!r} in service dependencies — "
            "engine libraries are engine-owned extras"
        )


def test_engine_libraries_live_in_extras_only() -> None:
    # The whisper engine's library is an OPTIONAL extra: absent from CI,
    # installed only where that engine actually runs.
    with (SERVICE_ROOT / "pyproject.toml").open("rb") as handle:
        pyproject = tomllib.load(handle)
    extras = pyproject["project"]["optional-dependencies"]
    assert any("faster-whisper" in dep for dep in extras["whisper"])
