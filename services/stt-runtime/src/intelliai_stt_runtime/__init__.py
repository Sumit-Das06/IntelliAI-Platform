"""IntelliAI transcription runtime.

Three independent responsibilities, three module groups (ADR-0016 shape):
``api/`` (HTTP binding), ``manager/`` (model lifecycle), ``engines/``
(inference execution). ``pipeline/`` feeds engines engine-neutral audio.
"""

__version__ = "0.1.0"
