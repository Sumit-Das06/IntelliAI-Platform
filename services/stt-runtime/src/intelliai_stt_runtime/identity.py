"""Who this runtime is — the one construction site for RuntimeMetadata."""

from typing import Final

from intelliai_runtime_contract import CONTRACT_VERSION, RuntimeMetadata
from intelliai_stt_runtime import __version__

SERVICE_NAME: Final = "stt-runtime"  # capability-named, never an engine name


def runtime_metadata() -> RuntimeMetadata:
    return RuntimeMetadata(
        service=SERVICE_NAME,
        service_version=__version__,
        contract_version=CONTRACT_VERSION,
    )
