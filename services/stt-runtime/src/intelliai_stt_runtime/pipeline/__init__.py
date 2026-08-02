"""Media ingestion — engine-neutral audio in, `DecodedAudio` out.

Step 3 ships the minimal stdlib WAV path so the architecture is provable
end-to-end without ffmpeg. Step 4 grows this into the full pipeline:
magic-byte sniffing, sandboxed ffmpeg decode to 16 kHz mono PCM, and VAD.
The `DecodedAudio` seam is what engines are written against — the pipeline
can change completely without an engine noticing.
"""

from intelliai_stt_runtime.pipeline.decode import DecodedAudio, decode_wav

__all__ = ["DecodedAudio", "decode_wav"]
