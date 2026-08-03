"""CI-enforced: runtime-core owns lifecycle, never inference (ADR-0019).

Static AST analysis in the style of the stt-runtime engine-isolation
suite, so the rules hold for every module — including ones added after
this test was written:

Rule 1: no module may import a foundation-model library — runtime-core
        never knows what a model does.
Rule 2: no module may import a capability package (a runtime, the
        gateway, the evaluation framework) — dependencies point AT
        runtime-core, never out of it.
Rule 3: no module may import server transport — runtime-core is machinery
        inside a service, not a service. (httpx is allowed: it is the
        ArtifactStore's download client, not a server.)
Rule 4: imports from the runtime contract are limited to error
        vocabulary — capability schemas are exactly what this package
        must never know.
"""

import ast
import tomllib
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SRC = PACKAGE_ROOT / "src" / "intelliai_runtime_core"

FOUNDATION_MODEL_LIBS = {
    "faster_whisper",
    "ctranslate2",
    "whisper",
    "kokoro",
    "misaki",
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

CAPABILITY_PACKAGES = {
    "intelliai_stt_runtime",
    "intelliai_tts_runtime",
    "intelliai_api",
    "intelliai_evaluation",
}

SERVER_TRANSPORT_LIBS = {"fastapi", "starlette", "uvicorn"}

# The one sanctioned slice of contract vocabulary: the error taxonomy.
ALLOWED_CONTRACT_IMPORTS = {"RuntimeErrorType"}


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


def test_never_imports_foundation_model_libraries() -> None:
    for module in modules():
        offending = import_roots(module) & FOUNDATION_MODEL_LIBS
        assert not offending, (
            f"{module.relative_to(PACKAGE_ROOT)} imports foundation-model "
            f"libraries {sorted(offending)} — runtime-core never knows what "
            "a model does (ADR-0019)"
        )


def test_never_imports_capability_packages() -> None:
    for module in modules():
        offending = import_roots(module) & CAPABILITY_PACKAGES
        assert not offending, (
            f"{module.relative_to(PACKAGE_ROOT)} imports capability package "
            f"{sorted(offending)} — dependencies point AT runtime-core, "
            "never out of it (ADR-0019)"
        )


def test_never_imports_server_transport() -> None:
    for module in modules():
        offending = import_roots(module) & SERVER_TRANSPORT_LIBS
        assert not offending, (
            f"{module.relative_to(PACKAGE_ROOT)} imports server transport "
            f"{sorted(offending)} — runtime-core is machinery inside a "
            "service, not a service"
        )


def test_contract_imports_are_error_vocabulary_only() -> None:
    for module in modules():
        tree = ast.parse(module.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            if not (node.module or "").startswith("intelliai_runtime_contract"):
                continue
            imported = {alias.name for alias in node.names}
            offending = imported - ALLOWED_CONTRACT_IMPORTS
            assert not offending, (
                f"{module.relative_to(PACKAGE_ROOT)} imports contract names "
                f"{sorted(offending)} — runtime-core may use error "
                "vocabulary only, never capability schemas (ADR-0019)"
            )


def test_dependencies_carry_no_model_libraries() -> None:
    with (PACKAGE_ROOT / "pyproject.toml").open("rb") as handle:
        pyproject = tomllib.load(handle)
    dependencies = " ".join(pyproject["project"]["dependencies"]).lower()
    for lib in FOUNDATION_MODEL_LIBS:
        assert lib.replace("_", "-") not in dependencies, (
            f"foundation-model library {lib!r} in runtime-core dependencies"
        )
