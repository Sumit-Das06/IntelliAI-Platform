"""CI-enforced boundaries (ADR-0016/0018), active from day one.

Rule 1: only engines/ modules may import foundation-model libraries — and
        the denylist already names the Kokoro chain (kokoro, misaki) plus
        the GPL espeak wrappers, which per the M3 license verdict may
        never be imported in-process ANYWHERE, engines included.
Rule 2: engines/ must not import transport (engines are pure adapters).
Rule 3: the service's own dependency list carries no foundation-model
        library — engine libraries arrive as engine-owned extras (step 4).
Rule 4: no voice asset files exist in the repo — voices are hash-pinned
        artifact files (step 4), never checked in.

Static AST analysis, so the rules hold for every module — including ones
added after this test was written.
"""

import ast
import tomllib
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]
SRC = SERVICE_ROOT / "src" / "intelliai_tts_runtime"

FOUNDATION_MODEL_LIBS = {
    "kokoro",
    "misaki",
    "faster_whisper",
    "ctranslate2",
    "torch",
    "torchaudio",
    "tensorflow",
    "transformers",
    "onnxruntime",
    "openvino",
    "vllm",
    "librosa",
    "soundfile",
    "numpy",
}

# GPL-3.0 espeak-ng wrappers: in-process import is a derivative-work risk
# (M3 design review §8). Banned EVERYWHERE in this service, engines
# included — the only acceptable espeak integration is a subprocess exec
# boundary, and that decision goes through review first.
GPL_PHONEMIZER_LIBS = {"phonemizer", "phonemizer_fork", "espeakng", "espeak_phonemizer"}

TRANSPORT_LIBS = {"fastapi", "starlette", "uvicorn", "httpx", "requests", "aiohttp"}

AUDIO_ASSET_SUFFIXES = {".wav", ".mp3", ".ogg", ".flac", ".pt", ".pth", ".onnx", ".bin", ".npz"}


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


def test_gpl_phonemizers_are_banned_everywhere_including_engines() -> None:
    for module in modules():
        offending = import_roots(module) & GPL_PHONEMIZER_LIBS
        assert not offending, (
            f"{module.relative_to(SERVICE_ROOT)} imports GPL espeak wrapper "
            f"{sorted(offending)} — in-process phonemization is a license "
            "verdict violation (M3 design review §8)"
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
                assert not node.module.startswith("intelliai_tts_runtime.api"), (
                    f"{module.relative_to(SERVICE_ROOT)} imports the api layer"
                )


def test_service_dependencies_are_provider_independent() -> None:
    with (SERVICE_ROOT / "pyproject.toml").open("rb") as handle:
        pyproject = tomllib.load(handle)
    dependencies = " ".join(pyproject["project"]["dependencies"]).lower()
    for lib in FOUNDATION_MODEL_LIBS | GPL_PHONEMIZER_LIBS:
        assert lib.replace("_", "-") not in dependencies, (
            f"library {lib!r} in service dependencies — engine libraries "
            "are engine-owned extras; phonemizers are banned outright"
        )
    # Engine libraries live in engine-owned extras ONLY, and no extra may
    # name a GPL phonemizer directly (the transitive presence on disk is
    # neutralized by the engine's license firewall — see engines/kokoro.py).
    extras = pyproject["project"]["optional-dependencies"]
    assert set(extras) == {"kokoro"}
    assert any(dep.startswith("kokoro") for dep in extras["kokoro"])
    extra_deps = " ".join(dep for deps in extras.values() for dep in deps).lower()
    for lib in GPL_PHONEMIZER_LIBS:
        assert lib.replace("_", "-") not in extra_deps


def test_no_voice_or_model_assets_in_the_repo() -> None:
    offending = [
        path
        for path in SERVICE_ROOT.rglob("*")
        if path.is_file() and path.suffix.lower() in AUDIO_ASSET_SUFFIXES
    ]
    assert not offending, (
        f"asset files {offending} in the service tree — voices and weights "
        "are hash-pinned artifacts in the store, never repo files"
    )
