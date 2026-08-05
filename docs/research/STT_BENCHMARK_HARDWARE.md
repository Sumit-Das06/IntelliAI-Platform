# IntelliAI Benchmark Environment Recording Specification

| | |
|---|---|
| **Status** | PROPOSED (Gate 3 design, 2026-08-05) |
| **Version** | 0.1 |
| **Role** | Exactly what must be recorded about hardware, software, and deployment for a benchmark to be interpretable years later. Companion to [STT_BENCHMARK_PROCEDURE.md](STT_BENCHMARK_PROCEDURE.md). |
| **Scope note** | Capability-generic. Nothing here is recognition-specific; generation benchmarks should adopt the same block. |

---

## 0. Why this is its own document

**[FACT]** "Same hardware class" appears in the evaluation methodology as a comparability
condition but exists **nowhere in code** — `_comparability` emits no hardware finding. And
the one machine we have measured on is already spelled **three different ways** across
committed records.

A comparability condition that is stated in prose and unenforced in schema is not a
condition. This document defines the fields; the record schema makes them structural.

---

## 1. `EnvironmentIdentity`

### 1.1 Compute — CPU

```
cpu_model            str    # exact vendor string, verbatim
cpu_physical_cores   int
cpu_logical_threads  int
cpu_base_clock_mhz   int | None
cpu_boost_clock_mhz  int | None
```

### 1.2 Memory and storage

```
ram_total_mib   int
ram_type        str | None    # e.g. DDR5-5600
storage_class   str           # nvme_ssd | sata_ssd | hdd | network
```

### 1.3 Accelerator — vendor-neutral by construction

```
accelerator:  AcceleratorIdentity | None = None

device_class        str                    # gpu | npu | asic | none
device_model        str
device_count        int
device_memory_mib   int | None             # None where memory is unified
driver_or_runtime   str
attributes          dict[str, str] = {}    # stack-specific pins
```

**This shape is deliberate.** A CUDA-shaped, all-required block (`vram_mib`,
`compute_capability`, `driver_version`) cannot be filled honestly by a device with unified
memory, no discrete VRAM, or no compute-capability analogue — an NPU, an inference ASIC,
anything not shaped like a 2026 NVIDIA part. Under an all-required schema every measurement
on such a device would be automatically incomplete and structurally excluded from promotion,
**because of a field shape rather than anything about the measurement's quality**. That is
the exact failure mode this system refuses everywhere else.

**`not_applicable` is distinct from `unknown`.** A device that *has* no VRAM is
`not_applicable` and does **not** degrade the record's completeness. A field we simply could
not read is `unknown`, is enumerated in `unknown_fields`, and **does** degrade completeness.

### 1.4 Threading and numerics — the field most often forgotten

```
thread_config   dict[str, int]   # OMP_NUM_THREADS, MKL_NUM_THREADS, torch threads, ORT intra/inter
blas_backend    str | None
compute_type    str              # int8 | int8_float16 | float16 | float32 | bf16
```

**[FACT]** No thread-count field exists anywhere in the current schemas, yet the runtime
architecture's capacity constants are functions of it, and CPU ASR throughput is strongly
thread-sensitive. A CPU benchmark without a recorded thread configuration is not
reproducible.

### 1.5 Machine state

```
virtualisation   str    # bare_metal | vm | container_on_shared_host | cloud_instance
power_profile    str | None
otherwise_idle   bool   # asserted, not assumed
```

---

## 2. `SoftwareIdentity`

```
os_name, os_version, kernel_version
container_runtime, image_digest        # digest, not tag — tags move
python_version
package_versions   dict[str, str]      # the engine library and its numeric stack
```

**Image digest, never tag.** A tag is a moving pointer; a digest is the artifact.

---

## 3. `VersionIdentity`

```
platform_git_commit
evaluation_package_version
methodology_version
contract_version
```

---

## 4. `DeploymentIdentity`

```
topology          str    # container | native | gateway_fronted
max_concurrency   int
max_queue         int
resource_limits   dict[str, str]   # cgroup/container limits, if any
gateway_present   bool
```

**[FACT]** Pool configuration is already self-described at `/info`
(`pool{admitted, max_concurrency, max_queue}`), so per Rule LF the harness reads it rather
than accepting it as a flag.

---

## 5. `StackIdentity`

```
serving_stack    str                   # free string, enumerated states preferred
engine_module    str
quantization     str | None
extra            dict[str, str] = {}
```

**Free string, deliberately.** **[FACT]** The candidate universe already spans CTranslate2,
whisper.cpp/GGUF, ONNX Runtime, transformers, PEFT-in-inference, NeMo/Riva/Triton/TensorRT,
vLLM, fairseq2, moshi/Rust/MLX and mistral-common. Three fixed strings
(`engine`/`engine_version`/`compute`) cannot describe that space, and an enum would be
obsolete within a year. The ban on free-form identifiers applies to **metric names**, whose
comparability depends on exact matching; a serving-stack label is descriptive metadata read
by humans.

---

## 6. Reference hardware across years

**The honest position: numbers taken on retired hardware do not become comparable again.**

Three mechanisms manage this without pretending otherwise:

1. **`hardware_class`** — a coarse, declared label (e.g. `cpu-x86-consumer-2026`) recorded
   on every run. `_comparability` blocks on a class mismatch.
2. **A bridging run.** When reference hardware is replaced, the **incumbent is re-measured
   on the new machine before any challenger is**. That produces two records of the same
   artifact across the boundary, which is what makes the era shift interpretable. This is
   the same "re-baseline the incumbent first" pattern already required on judge change —
   applied to hardware, where it was missing.
3. **Era labelling.** Records carry their hardware class permanently, so a five-year-old
   number is readable as *"the incumbent on 2026 consumer CPU"* rather than silently
   compared to a 2031 measurement.

Performance numbers across a hardware-class boundary are compared **only** through a
bridging run. Correctness numbers are unaffected by hardware, except through the judge-host
effect documented in the procedure.

*Change log: 0.1 (2026-08-05) — initial design (Gate 3).*
