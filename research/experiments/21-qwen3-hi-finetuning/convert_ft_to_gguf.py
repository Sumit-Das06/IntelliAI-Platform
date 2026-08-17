"""M21 Phase 13: fine-tuned HF checkpoint -> serving GGUF, by TEMPLATE REWRITE.

Mainline llama.cpp registers no Qwen3-ASR conversion; the official
ggml-org text GGUF is encoded as `qwen3vl` and its 311 tensors are
exactly the thinker's text side (model.* + lm_head). Our fine-tune
FROZE the audio tower, so:

- the official mmproj is reused BYTE-FOR-BYTE (tower unchanged);
- the text GGUF is produced by copying the official file's structure —
  every metadata key, tensor name, ordering, and per-tensor ggml type —
  and replacing only the tensor PAYLOADS with values quantized from the
  fine-tuned safetensors. Identical structure is what guarantees the
  pinned b10344 server accepts the artifact; only the weights differ.

The same rewrite applied to the BASE weights is the pipeline's control:
if base-rewritten behaves like the official artifact on the frozen
benchmark, the path is sound and the fine-tuned artifact's deltas are
attributable to training, not conversion.

Run with the b10344-exact gguf-py (PyPI gguf==0.19.0 matches that
tree's version):

    uv run --no-sync --with "gguf==0.19.0" --with ml_dtypes \
        python convert_ft_to_gguf.py --checkpoint <hf dir> \
        --template models/qwen3-asr-0.6b/v1/Qwen3-ASR-0.6B-Q8_0.gguf \
        --out <file>
"""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path
from typing import Any

import numpy as np


def load_safetensors(path: Path) -> dict[str, np.ndarray]:
    """Minimal single-file safetensors reader (bf16 -> float32)."""
    import ml_dtypes  # via gguf's numpy ecosystem; bf16 view support

    with path.open("rb") as handle:
        header_len = struct.unpack("<Q", handle.read(8))[0]
        header = json.loads(handle.read(header_len))
        blob = handle.read()
    tensors: dict[str, np.ndarray] = {}
    for name, meta in header.items():
        if name == "__metadata__":
            continue
        start, end = meta["data_offsets"]
        raw = blob[start:end]
        dtype = meta["dtype"]
        if dtype == "BF16":
            array = np.frombuffer(raw, dtype=ml_dtypes.bfloat16).astype(np.float32)
        elif dtype == "F32":
            array = np.frombuffer(raw, dtype=np.float32)
        elif dtype == "F16":
            array = np.frombuffer(raw, dtype=np.float16).astype(np.float32)
        else:
            msg = f"unsupported dtype {dtype} for {name}"
            raise ValueError(msg)
        tensors[name] = array.reshape(meta["shape"])
    return tensors


def hf_name_for(gguf_name: str) -> str:
    """GGUF tensor name -> the thinker checkpoint's HF tensor name."""
    fixed = {
        "token_embd.weight": "thinker.model.embed_tokens.weight",
        "output.weight": "thinker.lm_head.weight",
        "output_norm.weight": "thinker.model.norm.weight",
    }
    if gguf_name in fixed:
        return fixed[gguf_name]
    if gguf_name.startswith("blk."):
        parts = gguf_name.split(".")
        layer = parts[1]
        rest = ".".join(parts[2:])
        mapping = {
            "attn_q.weight": "self_attn.q_proj.weight",
            "attn_k.weight": "self_attn.k_proj.weight",
            "attn_v.weight": "self_attn.v_proj.weight",
            "attn_output.weight": "self_attn.o_proj.weight",
            "attn_q_norm.weight": "self_attn.q_norm.weight",
            "attn_k_norm.weight": "self_attn.k_norm.weight",
            "attn_norm.weight": "input_layernorm.weight",
            "ffn_gate.weight": "mlp.gate_proj.weight",
            "ffn_up.weight": "mlp.up_proj.weight",
            "ffn_down.weight": "mlp.down_proj.weight",
            "ffn_norm.weight": "post_attention_layernorm.weight",
        }
        if rest in mapping:
            return f"thinker.model.layers.{layer}.{mapping[rest]}"
    msg = f"no HF mapping for GGUF tensor {gguf_name!r}"
    raise ValueError(msg)


def main() -> int:
    import gguf
    from gguf import GGUFReader, GGUFWriter

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--checkpoint", type=Path, required=True, help="HF dir with model.safetensors"
    )
    parser.add_argument("--template", type=Path, required=True, help="official text GGUF")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    tensors = load_safetensors(args.checkpoint / "model.safetensors")
    reader = GGUFReader(str(args.template))

    architecture = None
    for field in reader.fields.values():
        if field.name == "general.architecture":
            architecture = str(bytes(field.parts[field.data[0]]), "utf-8")
    if architecture is None:
        msg = "template carries no general.architecture"
        raise ValueError(msg)

    writer = GGUFWriter(str(args.out), architecture)
    skip = {
        "general.architecture",  # the writer emits it itself
        "GGUF.version",
        "GGUF.tensor_count",
        "GGUF.kv_count",
    }
    for field in reader.fields.values():
        if field.name in skip:
            continue
        field_type = field.types[0]
        if field_type == gguf.GGUFValueType.ARRAY:
            item_type = field.types[1]
            if item_type == gguf.GGUFValueType.STRING:
                value: Any = [str(bytes(field.parts[idx]), "utf-8") for idx in field.data]
            else:
                value = [field.parts[idx].tolist()[0] for idx in field.data]
            writer.add_array(field.name, value)
        elif field_type == gguf.GGUFValueType.STRING:
            writer.add_string(field.name, str(bytes(field.parts[field.data[0]]), "utf-8"))
        else:
            scalar = field.parts[field.data[0]].tolist()[0]
            adders = {
                gguf.GGUFValueType.UINT8: writer.add_uint8,
                gguf.GGUFValueType.INT8: writer.add_int8,
                gguf.GGUFValueType.UINT16: writer.add_uint16,
                gguf.GGUFValueType.INT16: writer.add_int16,
                gguf.GGUFValueType.UINT32: writer.add_uint32,
                gguf.GGUFValueType.INT32: writer.add_int32,
                gguf.GGUFValueType.UINT64: writer.add_uint64,
                gguf.GGUFValueType.INT64: writer.add_int64,
                gguf.GGUFValueType.FLOAT32: writer.add_float32,
                gguf.GGUFValueType.FLOAT64: writer.add_float64,
                gguf.GGUFValueType.BOOL: writer.add_bool,
            }
            adders[field_type](field.name, scalar)

    replaced = 0
    for tensor in reader.tensors:
        hf_name = hf_name_for(tensor.name)
        if hf_name not in tensors and hf_name == "thinker.lm_head.weight":
            # Tied embeddings: transformers deduplicates the tied copy on
            # save; the GGUF's output.weight carries the same values.
            hf_name = "thinker.model.embed_tokens.weight"
        source = tensors[hf_name]
        expected_shape = tuple(int(d) for d in reversed(tensor.shape))
        if tuple(source.shape) != expected_shape:
            msg = f"{tensor.name}: checkpoint shape {source.shape} != template {expected_shape}"
            raise ValueError(msg)
        target_type = gguf.GGMLQuantizationType(tensor.tensor_type)
        if target_type in (gguf.GGMLQuantizationType.F32, gguf.GGMLQuantizationType.F16):
            data = source.astype(
                np.float32 if target_type == gguf.GGMLQuantizationType.F32 else np.float16
            )
            writer.add_tensor(tensor.name, data, raw_dtype=target_type)
        else:
            quantized = gguf.quants.quantize(source.astype(np.float32), target_type)
            writer.add_tensor(tensor.name, quantized, raw_dtype=target_type)
        replaced += 1

    writer.write_header_to_file()
    writer.write_kv_data_to_file()
    writer.write_tensors_to_file()
    writer.close()
    print(f"wrote {args.out} ({replaced} tensors, architecture {architecture})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
