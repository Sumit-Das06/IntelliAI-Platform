# IntelliAI Benchmark Hardware Profiles

| | |
|---|---|
| **Status** | PROPOSED v0.2 (Gate 4, 2026-08-05) — IN FORCE only on founder approval. Verified 2026-08-05; three corrections below. |
| **Corrections from verification** | **(1)** The claim "no field is invented" does **not** hold: `hardware_class`, `unknown_fields`, and a `SoftwareIdentity` notes field are **not** declared in [STT_BENCHMARK_HARDWARE.md](STT_BENCHMARK_HARDWARE.md). They are proposed *additions* and must be treated as prerequisites, not as present-tense spec fields. **(2)** `unknown` / `not_applicable` sentinels are assigned in places to `int`-typed fields (`device_memory_mib`, `cpu_base_clock_mhz`), which cannot hold a string — those fields take `None` plus a `Determination`. **(3)** Two founder items ask to "append members" to `storage_class` and `virtualisation`; both are plain `str` in the authority document, not enums, so no append is needed and no DECIDE item is warranted. **(4)** Profile ids are `HW1`–`HW6`, not `P1`–`P6` — `P<n>` collided with campaign phases. |
| **Version** | 0.1 |
| **Role** | The named, stable set of machine profiles a benchmark may be executed on, and the exact environment identity each one records. Instantiates [STT_BENCHMARK_HARDWARE.md](STT_BENCHMARK_HARDWARE.md) — that document defines the *fields*; this one defines the *machines* and states which of them exist. |
| **Gate discipline** | **This document defines. It never measures.** No model is run, scored, ranked, or compared anywhere below. Every number quoted is either read from a committed record or read from a machine's own firmware/library introspection — none was produced by an inference run for this document. |
| **Companions** | [Methodology](STT_BENCHMARK_METHODOLOGY.md) · [Record](STT_BENCHMARK_RECORD.md) · [Procedure](STT_BENCHMARK_PROCEDURE.md) · [Corpora](STT_BENCHMARK_CORPORA.md) · [Prerequisites](2026-08-05-stt-gate3-prerequisites.md) |

---

## 0. Two disclosures before anything else

### 0.1 The gate-numbering drift, recorded rather than papered over

`RESEARCH_FRAMEWORK.md` (IN FORCE v0.2) numbers its gates: **Gate 3 = Promising review**
(grants *Promising*), **Gate 4 = benchmark plan** (founder approval grants *Approved for
Benchmark*), **Gate 5 = adoption recommendation**. The working session numbering has drifted
— "Gate 3" was used for methodology design and "Gate 5" is being spoken of as "execute".

Two consequences hold regardless of which numbering a reader uses:

- **[FACT]** No candidate holds *Approved for Benchmark*. `MODEL_LEDGER.md` records all 12
  screened lineages as **Researching**, and none has passed a Promising review. **This
  document, and the campaign plan it belongs to, may be written. Neither may be executed**
  until statuses move through the founder gate.
- **[FACT]** `RESEARCH_FRAMEWORK.md` §1 says research never owns benchmark *execution*: the
  evaluation plane produces measurements, and engineering sessions execute via
  `ml/evaluation`. Defining a hardware profile is a research act. Standing one up, and
  running anything on it, is an engineering act.

### 0.2 Our entire measurement history is one machine

**[FACT]** Every committed measurement in this repository — five evidence records, two
production benchmarks, six benchmark documents — carries the same host: an
**Intel Core i7-14650HX**. There is no second machine, no second architecture, no
accelerator measurement of any kind, and no measurement outside Windows 11.

**[FACT]** That machine is already spelled **four different ways** across committed
artifacts:

| Spelling | Where |
|---|---|
| `Intel Core i7-14650HX (Windows 11, native)` | `stt/results/2026-08-02-whisper-small.json`, `stt/results/2026-08-05-intelliai-stt-en.json`, `stt/results/2026-08-05-intelliai-stt-hi.json`, `tts/results/2026-08-03-kokoro-82m.json`, `tts/results/2026-08-03-kokoro-82m-repro.json` |
| `Intel Core i7-14650HX, Docker Desktop (WSL2), Windows 11` | `stt/benchmarks/2026-08-03-whisper-small-docker.json` |
| `Intel Core i7-14650HX (Windows 11, Docker Desktop/WSL2)` | `tts/benchmarks/2026-08-03-kokoro-82m-docker.json` |
| `Intel Core i7-14650HX, Windows 11, native` (prose) | six documents under `docs/benchmarks/` and `ml/evaluation/stt/benchmarks/` |

A free string is not an identity. This document replaces the free string with a **profile
label** and a structured `EnvironmentIdentity`, without editing a single historical record —
the legacy strings above are recorded here as the four aliases that resolve to profile **P1**.

---

## 1. The existence ladder

Every profile below carries one of three verdicts. **A profile that does not exist is a
prerequisite, not a plan**, and no session may be scheduled on it.

| Verdict | Meaning | What a campaign may do with it |
|---|---|---|
| **EXISTS** | The hardware is in our possession and has been used for a committed measurement. | Schedule sessions. |
| **PROCURABLE** | No decision blocks it; it needs money and setup time, both bounded and known. | Name it in a plan with its instantiation cost stated; schedule nothing until instantiated. |
| **HYPOTHETICAL** | An open founder decision, an unbuilt capability, or an unbought machine stands in front of it. | Record it so the vocabulary exists. Schedule nothing. |

A fourth state is used below where it is the honest answer: **EXISTS AS HARDWARE / DOES NOT
EXIST AS A PROFILE** — the metal is here, but the software path to it is not built.

---

## 2. `hardware_class` — the label scheme

**[FACT]** `hardware_class` is required by the Gate 3 environment spec and **is not enforced
anywhere in code**: `_comparability` emits no hardware finding at all. The mechanism below is
therefore a *design*, and its enforcement is prerequisite 3.1 plus a `_comparability` change.

**Scheme:** `<device-class>-<isa>-<tier>-<era-year>`, lowercase, hyphen-separated.

**Four laws:**

1. **Minted once, never renamed.** Renaming breaks era labelling, which is the whole point:
   a five-year-old number must stay readable as *"the incumbent on 2026 consumer CPU"*.
   New classes are **appended**; old ones are never deleted, even when the metal is scrapped.
2. **The era year is the year the class was minted**, not the year of the run. A 2029 run on
   the same box still records `cpu-x86-consumer-2026`.
3. **`hardware_class` encodes hardware only.** It does **not** encode virtualisation,
   container topology, thread configuration, or power profile. Those are separate
   `EnvironmentIdentity` fields — see the gap in §8.2.
4. **A class is minted when a *performance* comparison across a boundary must be blocked.**
   Correctness metrics are hardware-independent (methodology §6, subject to the judge-host
   effect); the class exists to fence wall-clock numbers.

| Profile | `hardware_class` | Existence |
|---|---|---|
| **P1** CPU reference | `cpu-x86-consumer-2026` | **EXISTS** |
| **P2** CPU production | `cpu-x86-server-2026` | **PROCURABLE** |
| **P3** GPU reference | `gpu-nvidia-consumer-2026` | **EXISTS AS HARDWARE / DOES NOT EXIST AS A PROFILE** |
| **P4** GPU production | `gpu-nvidia-datacenter-2026` | **HYPOTHETICAL** |
| **P5** Edge | `cpu-arm-edge-2026` | **HYPOTHETICAL** |
| **P6** Cloud | `cloud-x86-shared-2026` (family-qualified — §3.6) | **PROCURABLE** |

`cpu-x86-consumer-2026` is taken **verbatim from the Gate 3 environment spec's own example**
(§6.1 of that document). That is deliberate: the label our own spec used to illustrate the
mechanism is the label our own machine gets.

---

## 3. The six profiles

Each profile below fills the Gate 3 `EnvironmentIdentity` blocks (§1.1–§1.5) plus the
`SoftwareIdentity`, `DeploymentIdentity` and `StackIdentity.quantization` fields those
records need to be interpretable. **No field is invented.**

---

### 3.1 P1 — CPU reference · `cpu-x86-consumer-2026`

> **Existence: EXISTS.** This is the machine every committed number in the repository was
> measured on. It is the *only* profile with an incumbent baseline, and therefore the only
> profile on which a campaign can begin.
>
> **But: it exists as hardware, not as a record.** Every committed run describes it with a
> free string. Its thread configuration, power profile, virtualisation state and effective
> compute type are **unrecorded**, which is why the numbers in §3.1.6 cannot be explained.

#### 3.1.1 Compute — CPU **[FACT, read from this machine's firmware via `Win32_Processor`]**

```
cpu_model            "Intel(R) Core(TM) i7-14650HX"    # verbatim vendor string
cpu_physical_cores   16                                 # 8 P-core + 8 E-core [INFERENCE from 16C/24T]
cpu_logical_threads  24
cpu_base_clock_mhz   2200                               # firmware-reported
cpu_boost_clock_mhz  5200                               # [CLAIM — vendor datasheet, NOT machine-read]
```

**Two honesty notes that must travel with this block:**

- **The part is hybrid.** 16 cores / 24 threads is 8 P-cores (SMT, 2 threads each) + 8
  E-cores (1 thread each). A single `cpu_base_clock_mhz` / `cpu_boost_clock_mhz` pair cannot
  describe two core types with different clock ceilings. The recorded values are the P-core
  values. This is a **known imprecision in the Gate 3 field shape**, recorded rather than
  fixed here — fixing it is a schema change (append `cpu_core_topology`), i.e. a prerequisite.
- **`cpu_boost_clock_mhz` is a CLAIM.** We did not read 5200 MHz from the machine and we have
  never observed it sustained. Under the currently active power scheme (§3.1.5) it is almost
  certainly unreachable. It is recorded as a datasheet fact, not a measurement.

#### 3.1.2 Memory and storage **[FACT, read from this machine]**

```
ram_total_mib   32768        # 2 x 16 GiB installed; 32371 MiB visible to the OS
ram_type        "DDR5-5600"  # SMBIOSMemoryType 34 = DDR5; ConfiguredClockSpeed 5600
storage_class   "nvme_ssd"   # WD PC SN5000S, 1.02 TB
```

The ~397 MiB gap between installed and OS-visible is firmware/iGPU reservation. `ram_total_mib`
records **installed**, because that is the stable hardware fact; the visible figure belongs in
`SoftwareIdentity` notes.

#### 3.1.3 Accelerator — **the field that must not lie**

```
accelerator   None
```

**[FACT]** This chassis physically contains an **NVIDIA GeForce RTX 5070 Laptop GPU**
(8151 MiB, driver 591.91, compute capability 12.0) and an Intel UHD iGPU. **[FACT]** No
committed measurement used either: `engines/whisper.py:152` constructs
`WhisperModel(..., device="cpu", ...)` with `"cpu"` as a **literal**.

`accelerator = None` on this profile therefore means **"no accelerator participated in the
measured system"**, not *"the machine has no accelerator"*. The Gate 3 spec does not
distinguish these, and silently choosing `None` would tell a future reader the reference
machine was GPU-less — which is false, and which matters, because an idle discrete GPU still
consumes part of a laptop's shared power and thermal budget.

**Resolution, using only mechanisms that already exist:** the profile records
`accelerator = None` **and** carries a `Determination` (record schema §1.4) on every P1 run:

```
code        accelerator_present_unused
subject     cpu-x86-consumer-2026
state       not_measured
producer    harness
basis       fact
detail      NVIDIA GeForce RTX 5070 Laptop GPU (8151 MiB, driver 591.91, cc 12.0) and
            Intel UHD Graphics are physically present and share the chassis power and
            thermal budget. Neither participates in inference: device="cpu" is a literal
            in engines/whisper.py.
```

This is not a new field. It is the mechanism the record schema built for exactly this.

#### 3.1.4 Threading and numerics

```
thread_config   { "OMP_NUM_THREADS": 4, "MKL_NUM_THREADS": 4,
                  "ct2_intra_threads": 4, "ct2_inter_threads": 1,
                  "torch_num_threads": 4, "ort_intra_op": 4, "ort_inter_op": 1 }
blas_backend    "ctranslate2-onednn"        # CTranslate2 4.8.1 x86-64 GEMM path
compute_type    "int8"                      # effective, read back — see §5
```

Full rationale in §4. **[FACT]** These values are a **declaration this document makes**, not a
transcription of what the baselines used — because what the baselines used was never recorded.
That makes the first run under this policy a **succession event requiring a bridging run**
(§6.3).

#### 3.1.5 Machine state — the block that changes how our numbers should be read

```
virtualisation   "bare_metal"     # with the caveat below
power_profile    "<recorded per run>"
otherwise_idle   <asserted per run>
```

**[FACT, read from this machine]** `Win32_ComputerSystem.HypervisorPresent = True`. Windows 11
runs here on the Hyper-V **root** partition (WSL2 and Docker Desktop are installed and
running). The Gate 3 enum offers `bare_metal | vm | container_on_shared_host | cloud_instance`.
Neither `bare_metal` (implies no hypervisor) nor `vm` (implies a guest partition) is exactly
true. **Decision: record `bare_metal`** — the OS has direct hardware access and is not a guest
— **plus a `Determination`** naming hypervisor presence, because virtualisation-based security
imposes a real, unmeasured overhead. A `bare_metal_hypervisor_root` enum member would be a
legal append and is filed as a prerequisite (§9), **not** minted here.

**[FACT, read 2026-08-05]** The active Windows power scheme is a vendor-custom profile
(**GUID `64a64f24-65b9-4b56-befd-5ec1eaced9b3`, "Silent"**, ASUS TUF Gaming F16 FX608JPR),
and the battery was **discharging** at 96%.

**This is the sharpest hardware finding in the repository.** P1 is a **laptop**. Its sustained
clock is a function of power scheme, AC/battery state, chassis temperature and vendor fan
policy — and **no committed record captures any of them**. We do not know, and cannot now
learn, which power state the M2/M3/M5 baselines were taken in.

Therefore, on P1, `power_profile` is **mandatory in the runner and load-bearing**, recorded as
the composite `"<scheme-name>/<scheme-guid>/<ac|battery>"`, e.g.
`"Silent/64a64f24-65b9-4b56-befd-5ec1eaced9b3/ac"`. A P1 performance record without it is
**incomplete** under V-1.

**Standing condition for P1:** every P1 performance session runs **on AC power**, under a
single declared scheme, with the scheme recorded. Battery runs are permitted only as
explicitly-labelled power-sensitivity evidence and are never a baseline.

#### 3.1.6 The unexplained delta this profile exists to prevent

**[FACT]** Three committed records, same artifact (`whisper-small` v1, `cpu-int8`), same
engine (`faster-whisper` 1.2.1), same host string, same `"native"` topology:

| Record | `load_ms` | `warmup_ms` |
|---|---|---|
| `2026-08-02-whisper-small.json` (M2) | **1130.1** | 2074.9 |
| `2026-08-05-intelliai-stt-en.json` (M5) | **5500.2** | 2638.9 |
| `2026-08-05-intelliai-stt-hi.json` (M5) | **5500.2** | 2638.9 |

**[FACT]** The containerized baseline recorded model load at **907 ms cold / 713 ms warm**.

Model load time moved **4.9×** between two runs of the same artifact on the same machine, and
**nothing in either record explains it**. Candidate mechanisms — page-cache state, power
scheme, AC/battery, thread count, concurrent load — are exactly the fields this document makes
mandatory. **[INFERENCE, explicitly not asserted]** The active Silent/battery state observed
today is one such mechanism; we cannot attribute the delta to it, and we will not.

**[FACT]** The two M5 records share `load_ms 5500.2` and `warmup_ms 2638.9` identically —
one process served both language slices, so their startup economics are **not independent
observations**. Any P1 startup metric must record which records share a process.

#### 3.1.7 Software, deployment and stack (P1, as committed)

```
SoftwareIdentity
  os_name          "Microsoft Windows 11 Home"
  os_version       "10.0.26200"
  kernel_version   "26200"                  # Windows build; no separate kernel version
  container_runtime  "docker" | not_applicable   # per topology, §3.1.8
  image_digest       <digest, never tag>    # not_applicable on the native topology
  python_version   "3.12"                   # repo pin (.python-version); image is python:3.12-slim
  package_versions { "faster-whisper": "1.2.1", "ctranslate2": "4.8.1",
                     "onnxruntime": "1.28.0", "torch": "2.13.0", "numpy": "2.5.1" }

DeploymentIdentity
  topology          "gateway_fronted" | "container" | "native"    # per session
  max_concurrency   2      # runtime default, read from /info — never a flag (Rule LF)
  max_queue         8      # runtime default, read from /info
  resource_limits   {}     # [FACT] docker-compose.yml sets no cpus/mem_limit on stt-runtime
  gateway_present   <per session>

StackIdentity
  serving_stack   "ctranslate2"
  engine_module   "intelliai_stt_runtime.engines.whisper"
  quantization    "int8"
```

#### 3.1.8 P1 is two environments, and our history already crossed between them unbridged

**[FACT]** Our quality records were taken **native** (`"Windows 11, native"`) and our
production ladder was taken **containerized under Docker Desktop/WSL2**. Same chassis, same
`hardware_class` — but a different kernel (Linux in a WSL2 utility VM vs Windows), a different
allocator, a different scheduler, and a different memory ceiling.

**[FACT]** No `.wslconfig` exists on this machine, so WSL2 defaults apply.
**[CLAIM, documented WSL2 default behaviour]** those defaults are all logical processors and
**50% of host RAM** — approximately 16 GiB of the 32 GiB, i.e. the containerized topology has
**half the memory** of the native one.

P1 is therefore defined with **two named topologies** under one `hardware_class`:

| Topology | `virtualisation` | Used by | Memory available |
|---|---|---|---|
| **P1-native** | `bare_metal` (+ hypervisor-root Determination) | all committed quality records | ~32 GiB |
| **P1-container** | `vm` (WSL2 utility VM hosting Docker) | both committed production ladders | ~16 GiB [CLAIM] |

**The gap this exposes:** methodology §6.1 gates performance comparisons on *"same hardware
class and pool configuration"*. `virtualisation` is **not** in the predicate. Two records —
one native, one WSL2 — would pass the comparability check today and be compared. That is a
defect in the predicate, filed in §9.

---

### 3.2 P2 — CPU production · `cpu-x86-server-2026`

> **Existence: PROCURABLE.** Nothing decides against it; it needs a rented or owned box and a
> Linux deployment target. **[FACT]** No production deployment of IntelliAI exists anywhere
> today — `resolution.json` resolves everything to the single `stt-runtime` deployment, and
> the compose header's promised `prod` overlay is absent from `infra/compose/`.
>
> **Instantiation cost:** a dedicated (not shared-tenant) x86 server with fixed clocks; a
> Linux host; the existing `stt-runtime` image (already `python:3.12-slim`, already
> Linux/amd64 — **[FACT]** `docker version` reports server `29.3.1 / linux / amd64`); and a
> **bridging run of the incumbent** (§6). No code change. No founder decision.

| Field | Value |
|---|---|
| `cpu_model` | recorded verbatim at instantiation — **dedicated server-class x86-64, no hybrid P/E topology** |
| `cpu_physical_cores` | ≥ 8, declared |
| `cpu_logical_threads` | declared; SMT **disabled where the host permits it** (see §4.3) |
| `cpu_base_clock_mhz` / `cpu_boost_clock_mhz` | recorded; **fixed-frequency (no turbo) is preferred** and recorded as such |
| `ram_total_mib` | ≥ 32768, **ECC required** and noted in `SoftwareIdentity.package_versions`-adjacent notes |
| `ram_type` | recorded verbatim |
| `storage_class` | `nvme_ssd` (local). `network` is permitted but then `artifact_ensure_download_ms` measures the network, not the machine, and must say so. |
| `accelerator` | `None` — **and here `None` is literally true**, unlike P1 |
| `thread_config` | `OMP=4, MKL=4, ct2_intra=4, ct2_inter=1, torch=4, ort_intra=4, ort_inter=1` — §4 |
| `blas_backend` | `"ctranslate2-onednn"` |
| `compute_type` | `int8` (primary), `int8_float32`, `int16`, `float32` — §5 |
| `virtualisation` | `bare_metal` (dedicated) — **`container_on_shared_host` disqualifies the profile as a baseline** |
| `power_profile` | BIOS performance profile recorded verbatim; **C-states and turbo policy declared** |
| `otherwise_idle` | `true`, asserted per P-9 — achievable here in a way it is not on P6 |
| **not_applicable** | the whole `accelerator` block |

**Why this profile is second and not first:** it has no incumbent baseline. Its first act must
be a bridging run of the incumbent (§6.3), or every number it produces is uncomparable to
everything we own.

---

### 3.3 P3 — GPU reference · `gpu-nvidia-consumer-2026`

> **Existence: EXISTS AS HARDWARE / DOES NOT EXIST AS A PROFILE.**
>
> **[FACT, read from this machine]** The reference chassis contains an **NVIDIA GeForce
> RTX 5070 Laptop GPU**: `nvidia-smi` reports 8151 MiB, driver **591.91**, compute capability
> **12.0**. The installed **CTranslate2 4.8.1 is a CUDA-capable build**:
> `get_cuda_device_count()` returns **1**, and `get_supported_compute_types('cuda')` returns
> **7** types. The metal and the library are both here.
>
> **What does not exist** is every part of the path to them.

**Six concrete blockers, all verified:**

1. **[FACT]** `device="cpu"` is a **literal** at `services/stt-runtime/src/intelliai_stt_runtime/engines/whisper.py:152`.
2. **[FACT]** `config.py` has **no `device` setting**. It has `whisper_compute_type` and
   nothing else. **This directly contradicts ADR-0004/ADR-0015**, which state that services
   read `DEVICE`/`COMPUTE_TYPE` from environment with resolution in exactly one place per
   service (its config module), and whose acceptance test is *"moving a service to GPU changes
   nothing under `services/*/src`."* **That acceptance test fails today.**
3. **[FACT]** No CUDA image variant exists. `infra/docker/stt-runtime.Dockerfile` is
   `python:3.12-slim`, single-variant, no build argument for a CUDA base.
4. **[FACT]** No GPU compose overlay exists. `docker-compose.yml`'s header states *"Overlays
   live in `infra/compose/` (gpu, prod)"*; `infra/compose/` contains **`.gitkeep` and
   `multilingual.yml` only**.
5. **[FACT]** No accelerator sampling capability (prerequisite 3.3): no
   `nvidia`/`cuda`/`nvml` reference exists anywhere in `ml/evaluation`. `accelerator_memory_peak_mib`
   is **RESERVED** in the metric register for exactly this reason, so a GPU run today cannot
   record its own memory.
6. **[UNVERIFIED — and it must stay unverified here]** Whether this CTranslate2 build ships
   **sm_120** kernels for a compute-capability-12.0 Blackwell part. `get_cuda_device_count()`
   enumerating a device proves the driver is visible, **not** that kernels exist for it.
   Determining this requires loading a model onto the GPU, which is **execution** and is
   forbidden at this gate. It is a Gate-4-plan verification item, owned by engineering.

> **BLOCKED ON FOUNDER DECISION** — prerequisite **3.2** ("decide whether a GPU/accelerator
> tier exists at all"). Note the asymmetry worth putting in front of the founder: blockers 1–4
> are ~a day of engineering, blocker 5 is a real build, and the hardware is already paid for.

| Field | Value |
|---|---|
| `cpu_model` … `storage_class` | **identical to P1** — same chassis |
| `accelerator.device_class` | `gpu` |
| `accelerator.device_model` | `"NVIDIA GeForce RTX 5070 Laptop GPU"` |
| `accelerator.device_count` | `1` |
| `accelerator.device_memory_mib` | `8151` |
| `accelerator.driver_or_runtime` | `"nvidia-driver 591.91 / CUDA <runtime version recorded at instantiation>"` |
| `accelerator.attributes` | `{ "compute_capability": "12.0", "cudnn": "<pinned>", "ct2_build": "4.8.1" }` |
| `thread_config` | `OMP=4, MKL=4, ct2_intra=4, ct2_inter=1` — **still recorded**: audio decode, mel extraction and tokenisation stay on CPU. See §4.4. |
| `blas_backend` | `"cublas"` (recorded verbatim at instantiation) |
| `compute_type` | `float16` (primary), `int8_float16`, `bfloat16`, `int8_bfloat16`, `int8`, `int8_float32`, `float32` — §5 |
| `virtualisation` | `bare_metal` (+ hypervisor-root Determination, as P1) |
| `power_profile` | **load-bearing and more severe than P1** — a laptop dGPU shares one power and thermal envelope with the CPU. AC power is mandatory; the vendor performance mode is recorded. |
| `otherwise_idle` | must additionally assert **no display compositing load on the dGPU** |
| **not_applicable** | none |

**A structural caveat [INFERENCE]:** a laptop GPU sharing a power envelope with a 16-core CPU
is a poor *production* proxy and an excellent *feasibility* instrument. P3's honest role is
"does this candidate run on an accelerator at all, and what does it cost in VRAM" — not
"what will it cost in production". P4 is the production question, and P4 does not exist.

---

### 3.4 P4 — GPU production · `gpu-nvidia-datacenter-2026`

> **Existence: HYPOTHETICAL.** It requires all six P3 blockers cleared, **plus** a
> datacenter-class accelerator we do not own and have not costed, **plus** the founder
> decision at prerequisite 3.2 — which is the same decision, at a much larger number.
>
> **Instantiation cost:** rented accelerator capacity (or purchase), a CUDA image variant, a
> GPU compose overlay, accelerator sampling (3.3), a Linux host, and a bridging run.
> **[FACT]** ADR-0004's own future-review criterion names the trigger: *"sustained GPU
> utilization above ~50% on rented capacity → evaluate reserved/owned hardware"* — we have
> zero GPU utilisation, so that criterion cannot yet fire in either direction.

| Field | Value |
|---|---|
| `cpu_model` … | recorded at instantiation; host CPU still matters (preprocessing, §4.4) |
| `accelerator.device_class` | `gpu` |
| `accelerator.device_model` | recorded verbatim (datacenter inference class, ECC VRAM) |
| `accelerator.device_count` | declared; **>1 requires a declared placement policy** and a Determination if the engine cannot use them |
| `accelerator.device_memory_mib` | recorded; **not_applicable only if the part has unified memory** |
| `accelerator.driver_or_runtime` | driver + CUDA runtime, both pinned |
| `accelerator.attributes` | `{ "compute_capability", "cudnn", "mig_profile" \| "none", "ecc": "on" }` |
| `thread_config` | as P3; host thread count declared because preprocessing is CPU-bound |
| `compute_type` | `float16` / `bfloat16` primary; `int8_float16`, `int8_bfloat16` for quantised serving — §5 |
| `virtualisation` | `bare_metal` or `cloud_instance` — **recorded, and it changes the class** (a shared-tenant GPU instance is not this profile; it is P6 with an accelerator) |
| `power_profile` | datacenter power cap / persistence mode recorded verbatim |
| `otherwise_idle` | `true`; **MIG partitioning, if present, makes this assertion partial** and requires a Determination |
| **not_applicable** | `device_memory_mib` **only** on a unified-memory part |

> **BLOCKED ON FOUNDER DECISION** — prerequisite **3.2**, and additionally on capital
> allocation. Under ADR-0015, this is an economic decision weighed against measurements,
> and **the measurements that would inform it do not exist**. Recorded as a circularity, not
> resolved.

---

### 3.5 P5 — Edge · `cpu-arm-edge-2026`

> **Existence: HYPOTHETICAL.** There is no edge product promise, no aarch64 image, no ARM CI
> runner, no ARM machine, and no committed measurement outside x86-64. This profile exists in
> this document so that the *vocabulary* exists before someone needs it — nothing more.
>
> **Instantiation cost:** an ARM64 device; an aarch64 image variant (the Dockerfile is
> arch-agnostic, but `uv.lock` resolution and the `whisper` extra's wheels are not verified
> for aarch64); an ARM CI lane; and a **schema append** — see the storage gap below.

| Field | Value |
|---|---|
| `cpu_model` | recorded verbatim (ARM64 SoC) |
| `cpu_physical_cores` | declared; **often heterogeneous (big.LITTLE)** — same imprecision as P1's hybrid part, worse |
| `cpu_logical_threads` | typically equals physical cores (no SMT) |
| `cpu_base_clock_mhz` | recorded |
| `cpu_boost_clock_mhz` | **`not_applicable`** on parts with no turbo state — this is a genuine `not_applicable`, and the distinction from `unknown` matters (Gate 3 §1.3) |
| `ram_total_mib` | recorded; typically 4–16 GiB, i.e. **below the ~800 MiB flat footprint's comfortable headroom only for small artifacts** |
| `ram_type` | recorded (often LPDDR); `unknown` where the SoC does not expose it |
| `storage_class` | **GAP** — the enum is `nvme_ssd \| sata_ssd \| hdd \| network`. eMMC and microSD have **no honest member**. Filed as a prerequisite append (§9); **not minted here.** |
| `accelerator` | `None`, **or** `device_class: "npu"` with `device_memory_mib: not_applicable` (unified memory) — the exact case the Gate 3 vendor-neutral shape was designed for |
| `thread_config` | `OMP = <all performance cores>`, `ct2_intra = <all performance cores>`, `ct2_inter = 1`. **The §4 rule of 4 intra-threads per worker does not survive here** — see §4.5. |
| `blas_backend` | recorded verbatim (e.g. Ruy / oneDNN-aarch64 / Arm Compute Library) |
| `compute_type` | `int8`, `int8_float32`, `float32`. **`float16` and `bfloat16` are not CPU compute types in CTranslate2** — §5.3 |
| `virtualisation` | `bare_metal` |
| `power_profile` | **the dominant variable.** Passively cooled edge devices throttle within minutes; a ladder that does not record thermal state measures the heatsink. Declared as `"<governor>/<power-cap-W>/<cooling: passive\|active>"`. |
| `otherwise_idle` | `true`, asserted |
| **not_applicable** | `cpu_boost_clock_mhz` (no-turbo parts); `accelerator.device_memory_mib` (unified memory); `accelerator` entirely where no NPU exists |

---

### 3.6 P6 — Cloud · `cloud-x86-shared-2026`

> **Existence: PROCURABLE — trivially.** A cloud instance is a credit card away.
> **Its comparability is not.**

**A taxonomy problem I must not paper over.** The six-profile set mixes two axes: *compute
device* (CPU / GPU / edge) and *placement* (reference / production / cloud). "Cloud" is not a
hardware class — a cloud CPU instance and a cloud GPU instance are different hardware. Two
consequences, both taken rather than hidden:

1. **P6's `hardware_class` is family-qualified, not fixed.** The stable label is
   `cloud-x86-shared-2026`; a **concrete class is minted per instance family** the first time
   performance numbers are taken on it (e.g. `cloud-x86-shared-2026/<family>`), because
   "vCPU" is not a stable hardware description and two instances of different families share
   nothing but an ISA. A cloud instance carrying an accelerator is **P4 with
   `virtualisation: cloud_instance`**, not P6.
2. **P6 can never satisfy P-9.** **[FACT]** Procedure precondition P-9 requires the machine to
   be *"otherwise idle, asserted and recorded, not assumed"*. On shared tenancy this is
   **structurally unassertable**: noisy neighbours are invisible and unbounded.

**Therefore P6 records `otherwise_idle = false`** and carries a standing Determination:

```
code        tenancy_not_exclusive
subject     cloud-x86-shared-2026
state       undeterminable
producer    harness
basis       fact
detail      Shared-tenant instance. P-9 (otherwise idle) cannot be asserted. Wall-clock
            metrics from this profile are not comparable to any exclusive-tenancy profile
            and may not be cited as a baseline.
```

| Field | Value |
|---|---|
| `cpu_model` | recorded verbatim as the hypervisor reports it (often a family, not a part) |
| `cpu_physical_cores` | **`unknown`** where the instance exposes only vCPUs — and `unknown` **degrades completeness**, correctly |
| `cpu_logical_threads` | vCPU count (recorded) |
| `cpu_base_clock_mhz` / `cpu_boost_clock_mhz` | **`unknown`** — they exist, we cannot read them. **Not `not_applicable`.** |
| `ram_total_mib` | recorded |
| `ram_type` | **`unknown`** — typically unexposed |
| `storage_class` | `network` for remote-attached volumes, `nvme_ssd` for instance-local. This choice changes what `artifact_ensure_download_ms` means. |
| `accelerator` | `None` (a cloud accelerator instance is P4) |
| `thread_config` | pinned as §4, from **vCPU count**, with the caveat that vCPU ≠ core |
| `compute_type` | `int8` primary — §5 |
| `virtualisation` | **`cloud_instance`** |
| `power_profile` | **`not_applicable`** — not ours to set, not ours to observe |
| `otherwise_idle` | **`false`**, asserted false, with the Determination above |
| **not_applicable** | `power_profile`; the `accelerator` block |
| **unknown** (degrades completeness) | `cpu_physical_cores`, `cpu_base_clock_mhz`, `cpu_boost_clock_mhz`, `ram_type` |

**P6's honest role:** unit economics and deployability — *"what does an hour of this cost,
and does the image come up"*. It is **not** a performance baseline and its ladders are not
comparable to P1's. Saying so here prevents a cheap cloud number being read against our
incumbent later.

---

## 4. Thread policy — the field most often forgotten, made explicit

**[FACT]** No thread-count field exists anywhere in current schemas (Gate 3 §1.4), no
`OMP_NUM_THREADS`/`MKL_NUM_THREADS` appears anywhere in this repository, and
`load_faster_whisper` passes **neither `cpu_threads` nor `num_workers`**:

```python
model = WhisperModel(str(local_dir), device="cpu", compute_type=compute_type)
```

**[FACT, read from the installed libraries]** The defaults that therefore apply are
`WhisperModel(cpu_threads=0, num_workers=1)` → CTranslate2 `intra_threads=0` ("0 to use a
default value"), `inter_threads=1`.

**[INFERENCE, corroborated by our own record]** The committed ladder shows
`docker_cpu_percent_max` ≈ **899% / 909% / 904%** at c=5/10/20 against a runtime pool of
`max_concurrency=2`. Two workers × 4 OpenMP threads ≈ 8 threads ≈ 900% is consistent with a
default `intra_threads` of 4. **We are inferring our own configuration from a CPU percentage.**
That is precisely the situation prerequisite 3.4 exists to end.

### 4.1 The five laws

| # | Law |
|---|---|
| **T-1** | **Threads are declared, never defaulted.** Every profile pins `OMP_NUM_THREADS`, `MKL_NUM_THREADS`, the engine's intra/inter setting, and (where the stack applies) torch and ORT thread counts — **even when the pinned value equals the library default**. A default is not a record. |
| **T-2** | **The pinned value derives from physical performance cores** — never logical threads, never total cores. SMT siblings share execution units and inflate the count without adding GEMM throughput; on a hybrid part, E-cores are a **straggler class** inside barrier-synchronised OpenMP regions and can make a wider pool slower. |
| **T-3** | **`admission_concurrency × intra_threads ≤ physical performance cores.`** Beyond that point, added parallelism converts into context switching, which the ladder then reads as a "throughput plateau" that is really an oversubscription artefact. |
| **T-4** | **Per-worker `intra_threads` is fixed at 4 across every CPU profile** (P1, P2, P6). Concurrency scales with the box; per-worker width does not. This is what keeps `recognition_rtf` at c=1 comparable across CPU profiles — the alternative (scaling width with core count) makes every CPU profile a different ruler. P5 is the declared exception (§4.5). |
| **T-5** | **The recorded value is the *effective* configuration, read back — not the *intended* one.** Per **Rule LF**, since the serving process can observe its own thread and precision settings, `/info` must report them and the harness must have **no flag** for them. |

### 4.2 T-5 is buildable today, and that matters

**[FACT, verified at source]** CTranslate2 4.8.1 exposes, as readable model properties:
`compute_type`, `device`, `device_index`, `num_workers`, `num_active_batches`,
`num_queued_batches`. The effective configuration is **already introspectable**; nothing needs
inventing. Prerequisite 3.4 is therefore "surface these at `/info`", not "add a CLI flag" —
and Rule LF forbids the flag.

This also closes the silent-fallback hazard in §5.2.

### 4.3 P1 / P2 / P6 — the CPU rule instantiated

| Profile | Physical perf cores | `admission_concurrency` | `intra_threads` | Product | Headroom |
|---|---|---|---|---|---|
| **P1** | 8 P-cores (of 16C/24T) | 2 (runtime default, read from `/info`) | 4 | 8 | 8 E-cores left for the OS, ffmpeg decode, the harness itself, and the `docker stats` sampler |
| **P2** | declared (≥8) | `floor(perf_cores / 4)` | 4 | ≤ perf cores | ≥1 core reserved for the host |
| **P6** | vCPU count (a weaker fact) | `floor(vCPU / 4)`, min 1 | 4 | ≤ vCPU | recorded, but unenforceable under shared tenancy |

**P1's headroom rule is not decoration.** Precondition P-9 requires an otherwise-idle machine,
yet the harness, the ffmpeg decoder and the container-stats sampler all run on that same
machine during measurement. Leaving the E-core cluster unclaimed is how P-9 is made
approximately true rather than merely asserted — and the choice is **recorded**, so a future
reader can see it was a choice.

**SMT:** disabled at the host where the profile permits it (P2); where it cannot be disabled
(P1, P6), thread counts still derive from *physical* cores per T-2, and `cpu_logical_threads`
is recorded so the ratio is visible.

**One consequence to record, not resolve:** with `inter_threads=1` (the constructor default,
since `load_faster_whisper` sets only `compute_type`), the runtime's `max_concurrency=2`
admission slots do **not** map to two CTranslate2 workers. "Pool configuration" in the §6.1
comparability predicate is the **runtime's** pool, which is a different quantity from the
engine's worker count. Both must be recorded; conflating them would make two records look
comparable when their parallelism differs. Filed in §9.

### 4.4 P3 / P4 — thread policy still applies on GPU

Threads are **not** `not_applicable` on an accelerator profile. Audio decode (ffmpeg), mel
feature extraction, tokenisation and post-processing remain CPU work, and on short clips they
are a meaningful share of end-to-end latency. `thread_config` is recorded in full; what
changes is only that GEMM leaves the CPU. A GPU profile recording `thread_config = {}` would
be hiding a real cost centre.

### 4.5 P5 — the declared exception to T-4

Edge parts commonly have 4–8 total cores and heterogeneous clusters. Fixing per-worker width
at 4 while also fixing concurrency ≥1 saturates the device with a single request, which is
often the *correct* edge configuration (single-user, latency-first) but breaks the T-4
comparability invariant. **P5 therefore declares `intra_threads = <all performance cores>`,
`admission_concurrency = 1`, and records a Determination that its `recognition_rtf` is not
comparable to CPU-profile RTF under T-4.** Naming the break is the point; an unnamed break
becomes a silent cross-profile comparison.

### 4.6 Thread configuration is a succession boundary

Because our incumbent's thread configuration was never recorded, **declaring one is a change**
— even if the declared value turns out to equal what was running. The first run under this
policy is a bridging run (§6.3), not a continuation.

---

## 5. Quantization — real values only

### 5.1 What the platform actually supports today

**[FACT]** Exactly one quantization surface is wired: `whisper_compute_type: str = "int8"` in
`services/stt-runtime/.../config.py`, passed to CTranslate2 at load time
(`INTELLIAI_STT_WHISPER_COMPUTE_TYPE`). Under ADR-0015 and `MODEL_IDENTITY.md` §5, precision
is a property of the **build**, never of identity — which is why the committed records carry
`compute = "cpu-int8"` and `identity.build = "cpu-int8"`.

**[FACT, from CTranslate2 4.8.1's own docstring]** the complete valid token set is:

```
default · auto · int8 · int8_float32 · int8_float16 · int8_bfloat16 · int16 · float16 · bfloat16 · float32
```

**A vocabulary correction the Gate 4 plan must carry:** the Gate 3 environment spec's
`compute_type` comment lists `int8 | int8_float16 | float16 | float32 | bf16`. **`bf16` is not
a CTranslate2 token** — the real token is `bfloat16`. The comment is illustrative rather than
normative, but records must carry the engine's own string. Filed in §9 as a documentation fix,
**not** a schema change.

### 5.2 What each profile supports — verified, not assumed

**[FACT, read on this machine]** `ctranslate2.get_supported_compute_types('cpu')` returns
exactly **`{float32, int8_float32, int16, int8}`**, and `...('cuda')` returns
**`{float32, int8_float32, int8_float16, int8, float16, int8_bfloat16, bfloat16}`**.

| Profile | Primary | Also valid | Invalid / silently downgraded |
|---|---|---|---|
| **P1** CPU reference | **`int8`** (preserves the incumbent build) | `int8_float32`, `int16`, `float32` | `float16`, `bfloat16`, `int8_float16`, `int8_bfloat16` |
| **P2** CPU production | **`int8`** | `int8_float32`, `int16`, `float32` | as P1 (subject to re-verification on that CPU) |
| **P3** GPU reference | **`float16`** | `int8_float16`, `bfloat16`, `int8_bfloat16`, `int8`, `int8_float32`, `float32` | — |
| **P4** GPU production | **`float16`** or `bfloat16` | `int8_float16`, `int8_bfloat16`, `int8`, `float32` | verify per part at instantiation |
| **P5** Edge | **`int8`** | `int8_float32`, `float32` | `float16`, `bfloat16` (not CPU types); `int16` verify per SoC |
| **P6** Cloud | **`int8`** | `int8_float32`, `int16`, `float32` | as P1 |

**The silent-fallback hazard.** CTranslate2 accepts an unsupported `compute_type` and falls
back to a supported one. A record could therefore carry `compute_type = "float16"` while the
machine ran `float32` — a **wrong, plausible, permanent** entry in an append-only ledger. This
is the same failure shape as the Devanagari empty-reference hazard.

**Mandatory countermeasure:** `EnvironmentIdentity.compute_type` records the **effective**
value read back from the loaded model (`model.compute_type`, §4.2), never the requested one.
Where requested ≠ effective, both are recorded and a Determination is emitted. This uses no
new field: `compute_type` already exists, and `Determination` already exists.

### 5.3 Non-CTranslate2 stacks

Every other serving stack in the candidate universe (ONNX Runtime, transformers/PyTorch, NeMo,
fairseq2, vLLM, moshi) has its **own** quantization vocabulary, and **none of them is installed
in any service today** — `onnxruntime 1.28.0` and `torch 2.13.0` exist in the workspace
environment, but no `engines/` adapter uses them, and the STT image installs only the
`whisper` extra.

Therefore: **`StackIdentity.quantization` is a free string carrying the stack's own token**
(Gate 3 §5 deliberately made `StackIdentity` free-string for exactly this reason — the ban on
free-form identifiers applies to *metric names*, not to descriptive stack metadata). A profile
does **not** enumerate quantization values for a stack that has no adapter. Each new stack
brings its own row, at the time its adapter is built — that is a per-stack prerequisite, not a
gap in this document.

---

## 6. Hardware succession — applying the Gate 3 bridging-run policy

The policy is settled in `STT_BENCHMARK_HARDWARE.md` §6 and is **applied here, not
redesigned**. Its three mechanisms: `hardware_class` on every run; a **bridging run** in which
the incumbent is re-measured on the new machine **before any challenger is**; and permanent
era labelling.

### 6.1 The bridging run, made concrete

| Element | Value |
|---|---|
| **Artifact** | the incumbent — `whisper-small` v1, build `cpu-int8` (or the GPU build's direct equivalent when crossing to P3/P4) |
| **Corpus** | the same released, immutable corpus version, both sides |
| **Language** | one session per language (procedure §1); a bridge is not an excuse to merge slices |
| **Thread policy** | the §4 declaration, **identical on both sides** where the profile permits it |
| **Output** | two records, one per side of the boundary, each carrying **its own** `hardware_class`, sharing a `session_id` prefix |
| **Schema** | unchanged. No new metric, no new field, no new enum. |
| **Order** | **incumbent first, always.** A challenger measured on a new class before the bridge exists produces a number comparable to nothing. |

**A bridging run is not a promotion event and yields no verdict.** It exists so that two eras
can be read together, and it decides nothing about any candidate.

### 6.2 What crosses a boundary and what does not

**Performance numbers cross a `hardware_class` boundary only through a bridging run.**
Correctness numbers are hardware-independent — **with the one exception our own evidence
forces**: **[FACT]** in the committed `kokoro-82m` / `-repro` pair, with identical judge
artifact and version, 9 of 25 transcripts differed and `round_trip_wer` moved 0.5000 → 0.5042
because the judge ran on a **different host**. Where a judge is involved, judge *host* is part
of correctness comparability. Recognition records `judge = None` by law (A-0), so on the STT
path this constrains round-trip work, not the recognition ruler.

### 6.3 The five succession events we can already foresee

| # | Event | Bridge required | Status |
|---|---|---|---|
| **S-1** | **Declared thread policy first applied** (§4.6) | **Yes** — the incumbent's thread configuration is unrecorded, therefore unreproducible | **Imminent.** The first act of any campaign. |
| **S-2** | **P1-native ↔ P1-container** (§3.1.8) | **Yes** — different kernel, allocator, scheduler, and ~half the memory | **Already crossed, unbridged.** Our quality records are native; both production ladders are WSL2. A retrospective bridge is the cheapest honest fix. |
| **S-3** | **P1 → P2** (consumer laptop → dedicated server) | **Yes** | Pending P2 procurement |
| **S-4** | **CPU class → GPU class** (P1/P2 → P3/P4) | **Yes** — and note this is a *coexistence*, not a retirement: both eras stay live | Blocked on founder decision 3.2 |
| **S-5** | **P1 retirement** (the reference laptop replaced) | **Yes** | Not scheduled — but the laptop is a consumer part with a finite service life, and **when it dies unbridged, every performance number we own becomes uninterpretable.** S-1 is also the cheapest insurance against this. |

**S-5 deserves emphasis.** The bridging policy only works if the outgoing machine is still
alive when the incoming one arrives. A hardware succession that happens by failure rather than
by plan cannot be bridged. That is an argument for executing S-1 and S-3 early, and it is an
engineering-risk statement, not a candidate recommendation.

---

## 7. Which profiles are blocked on the GPU founder decision

**Prerequisite 3.2 — "Decide whether a GPU/accelerator tier exists at all" (type: DECIDE)** —
gates:

| Profile | Blocked | Nature of the block |
|---|---|---|
| **P3** GPU reference | **YES** | Decision + 4 small engineering items + 1 real build (accelerator sampling, 3.3) + 1 verification. **The hardware is already owned.** |
| **P4** GPU production | **YES** | Decision + capital + everything in P3 |
| **P1, P2, P5, P6** | No | P5 is blocked on a *product* decision (does an edge tier exist), which is a different question and is **not** filed as 3.2 |

**A circularity to put in front of the founder, recorded not resolved.** ADR-0015 says GPU
spend must be argued against numbers — *"GPU spend must now be argued against **numbers** (unit
economics per tier), which requires those numbers to exist"*. Producing those numbers requires
P3, and P3 is blocked on the decision the numbers are meant to inform. The cheapest cut is
P3-as-feasibility-only (the metal is paid for; the blockers are four small engineering items
plus one build), explicitly **not** as a production proxy — see §3.3's caveat.

**Secondary decision, currently unnamed anywhere:** ADR-0004/ADR-0015 promise `DEVICE` as
environment configuration with single-point resolution, and **the code does not implement it**
(`device="cpu"` literal; no `device` setting in `config.py`; no CUDA image; no GPU overlay
despite `docker-compose.yml` advertising one). **Whether or not a GPU tier is approved**, this
is an accepted ADR whose stated acceptance test fails today. That is a standing engineering
defect, and it is filed as such rather than bundled into the GPU decision.

---

## 8. `not_applicable` vs `unknown` — the discipline, per profile

Gate 3 §1.3 makes the distinction structural: `not_applicable` **does not** degrade a record's
completeness; `unknown` **does**, and must be enumerated in `unknown_fields`. Choosing the
wrong one either hides a gap or manufactures one.

### 8.1 The table

| Field | P1 | P2 | P3 | P4 | P5 | P6 |
|---|---|---|---|---|---|---|
| `cpu_*` | recorded | recorded | recorded | recorded | recorded (`boost` may be **N/A**) | `physical_cores`/`clocks` **unknown** |
| `ram_type` | recorded | recorded | recorded | recorded | recorded or **unknown** | **unknown** |
| `storage_class` | recorded | recorded | recorded | recorded | **enum gap** (§3.5) | recorded |
| `accelerator` (block) | **N/A** + Determination | **N/A** | recorded | recorded | **N/A** or NPU | **N/A** |
| `accelerator.device_memory_mib` | — | — | recorded | recorded (**N/A** if unified) | **N/A** (unified) | — |
| `thread_config` | recorded | recorded | recorded | recorded | recorded | recorded |
| `blas_backend` | recorded | recorded | recorded (`cublas`) | recorded | recorded | recorded |
| `compute_type` | recorded (**effective**) | recorded | recorded | recorded | recorded | recorded |
| `virtualisation` | `bare_metal` + Determination | `bare_metal` | `bare_metal` + Determination | `bare_metal`\|`cloud_instance` | `bare_metal` | `cloud_instance` |
| `power_profile` | **mandatory** | recorded | **mandatory** | recorded | **mandatory** | **N/A** |
| `otherwise_idle` | `true` asserted | `true` asserted | `true` asserted (+dGPU) | `true` (partial under MIG) | `true` asserted | **`false`** + Determination |
| `image_digest` | **N/A** on P1-native | recorded | recorded | recorded | recorded | recorded |

**The rule of thumb:** *"the thing does not exist"* → `not_applicable`. *"the thing exists and
we could not read it"* → `unknown`. **"the thing exists and we chose not to use it"** → the
field is `not_applicable`/`None` **and a `Determination` records the choice** (P1's idle GPU,
§3.1.3). That third case is not in the Gate 3 text; it is resolved here using only existing
mechanisms.

### 8.2 What `hardware_class` alone cannot fence

Methodology §6.1 gates performance comparison on *"same hardware class and pool
configuration"*. On the evidence above, that predicate is **insufficient**: it does not see
`virtualisation` (§3.1.8 — native vs WSL2 on one chassis), `thread_config` (§4),
`power_profile` (§3.1.5 — a laptop under a Silent scheme on battery), or effective
`compute_type` (§5.2). Four records could pass the predicate and share nothing that makes them
comparable.

This is a **defect in the predicate, not in the profiles**, and it is filed as a prerequisite
rather than fixed here — amending the comparability predicate is a methodology change.

---

## 9. Prerequisites this document settles, and the ones it creates

### 9.1 Layer 3 items this document answers

| # | Item | Status after this document |
|---|---|---|
| **3.1** | Define the CPU reference machine and its `hardware_class` | **Drafted** — P1, `cpu-x86-consumer-2026`, §3.1. Founder ratification still required (type DECIDE). |
| **3.2** | Decide whether a GPU/accelerator tier exists | **Sharpened, not answered** — §7 states exactly what is blocked, what it costs, and that the hardware is already owned. Still DECIDE. |
| **3.3** | Accelerator sampling capability | **Unchanged: BUILD.** `accelerator_memory_peak_mib` stays RESERVED. |
| **3.4** | Thread-configuration capture | **Specified** — §4, with the Rule LF resolution: surface at `/info`, no CLI flag. Still BUILD. |
| **3.5** | Hardware-succession bridging-run policy | **Applied, not redesigned** — §6, with five foreseen events, two of them already live. Still DECIDE (ratification). |

### 9.2 New prerequisites this document creates

| # | Item | Type | Why |
|---|---|---|---|
| **H-1** | Add `virtualisation`, `thread_config` and effective `compute_type` to the §6.1 comparability predicate | BUILD | §8.2 — four records can pass the current predicate sharing nothing comparable |
| **H-2** | `_comparability` emits a `different_hardware_class` finding (it emits **no** hardware finding today) | BUILD | The whole `hardware_class` mechanism is currently unenforced |
| **H-3** | Append a `virtualisation` member for hypervisor-root hosts (`bare_metal_hypervisor_root`) | DECIDE | §3.1.5 — neither `bare_metal` nor `vm` is true of our reference machine |
| **H-4** | Append `storage_class` members for embedded media (eMMC / SD) | DECIDE | §3.5 — P5 has no honest value |
| **H-5** | Append `cpu_core_topology` to `EnvironmentIdentity` for hybrid / big.LITTLE parts | DECIDE | §3.1.1 — one base/boost pair cannot describe two core types |
| **H-6** | Record the runtime pool and the engine worker count as **distinct** quantities | BUILD | §4.3 — `max_concurrency=2` with `inter_threads=1` are not the same parallelism |
| **H-7** | Fix `device` resolution: `DEVICE` in `config.py`, remove the `device="cpu"` literal | BUILD | §3.3 — an accepted ADR's stated acceptance test fails today |
| **H-8** | Correct `bf16` → `bfloat16` in the Gate 3 `compute_type` comment | BUILD (doc) | §5.1 — `bf16` is not an engine token |
| **H-9** | Retrospective **S-2 bridge** (P1-native ↔ P1-container) | BUILD | §6.3 — a boundary we already crossed without a bridge |

---

## 10. What this document does not decide

- **It names no candidate**, ranks nothing, scores nothing, and recommends no adoption. The
  only artifact named is `whisper-small` v1 in its role as the **incumbent** — the subject of
  every bridging run — because bridging is defined by re-measuring the incumbent.
- **It schedules no session.** Profiles are vocabulary; sessions are the campaign plan's
  business, and none may run before statuses move through the founder gate (§0.1).
- **It does not decide whether a GPU tier exists** (§7), whether an edge tier exists (§3.5), or
  what capital any profile is worth. Those are founder decisions, stated here with their costs
  and their circularities, and left open.
- **It measures nothing.** Every figure above was read from a committed record, from firmware,
  or from an installed library's own introspection. **No model was loaded and no inference was
  run to produce this document.**

*Change log: 0.1 (2026-08-05) — initial draft (Gate 4, designer 4). Defines six profiles,
states existence honestly for each, makes thread policy explicit for the first time, pins
quantization to verified engine tokens, and applies the Gate 3 bridging-run policy to five
foreseen succession events — two of which have already occurred.*
