# DK-2500 Hardware and Software Truth

Truth ID: `P4-DK2500-TRUTH-20261003-01`

Capture date: `2026-10-03`

Status: `CAPTURED_WITH_EXPLICIT_GAPS — HUMAN REVIEW PENDING`

Scope: read-only Phase 4 entry evidence. No model load, compile, inference, benchmark, package
installation, driver change or system update was performed.

Machine-readable record:
`evidence/phase4_0_truth/dk2500_truth_20261003.json`.

## Connection truth

- Direct Ethernet: local `192.168.77.1/24` to DK-2500 `enp1s0` at `192.168.77.2/24`.
- SSH identity: `hepintel@hepintelpc` using a dedicated key.
- The direct link has no default route and does not provide DK-2500 Internet access.
- Tailscale is installed on the DK-2500, but it is not the transport used for this capture.

## Hardware truth

| Component | Observed identity or state | Evidence boundary |
|---|---|---|
| CPU | Intel Core Ultra 5 225U, 12 physical cores reported, 14 logical CPUs | `lscpu` |
| Memory | `7,852,589,056` bytes available to the OS; 2 GiB swap | Module count, vendor and channel topology remain unknown |
| Storage | 119.2 GiB SATA SSD; root filesystem had about 60 GiB free | Device serial intentionally excluded from the tracked report |
| Firmware | AMI BIOS `5.32`, dated `2026-04-01` | Board vendor/model DMI fields are `Default string` |
| iGPU | PCI `8086:7d41`, Arrow Lake-U graphics, kernel driver `i915` | `/dev/dri/renderD128` exists; OpenVINO GPU is not visible |
| NPU | PCI `8086:7d1d`, kernel driver `intel_vpu` | `/dev/accel/accel0` exists; OpenVINO reports Intel AI Boost |
| Ethernet | Four Intel I210 controllers, PCI `8086:1533`, driver `igb` | `enp1s0` is the active direct-maintenance port |

## Initial idle observation

- CPU package temperature: approximately `47°C` at the bounded capture instant.
- ACPI thermal zone: approximately `27.8°C`.
- Power profile: `performance`.
- Intel P-state: `active`; `no_turbo=0`.
- `thermald`: active.

This is one entry observation, not a frozen thermal or power baseline. Physical power supply,
cooling configuration, ambient conditions and steady-state idle duration remain to be recorded.

## Software truth

| Layer | Observed state |
|---|---|
| OS | Ubuntu 24.04.4 LTS |
| Kernel | `6.17.0-35-generic` |
| Python | `/usr/bin/python3`, Python 3.12.3 |
| OpenVINO | `2026.2.1-21919-ede283a88e3-releases/2026/2` |
| OpenVINO CPU | Visible; full name `Intel(R) Core(TM) Ultra 5 225U` |
| OpenVINO NPU | Visible; full name `Intel(R) AI Boost` |
| OpenVINO GPU | Not visible |
| NPU driver family | `1.33.0.20260529-26625960453~ubuntu24.04` |

## GPU boundary finding

The following facts coexist:

1. the iGPU PCI function and `i915` kernel driver are present;
2. `/dev/dri/renderD128` exists and the user belongs to the `render` group;
3. the OpenVINO 2026.2.1 GPU plugin package is installed;
4. the generic OpenCL loader is installed;
5. the Intel GPU OpenCL ICD / compute-runtime package is not installed;
6. no Intel vendor ICD is registered under `/etc/OpenCL/vendors`;
7. OpenVINO therefore reports only `CPU` and `NPU`.

Strongest supported conclusion: the current userspace stack is incomplete for OpenVINO GPU device
discovery. This does not prove a GPU hardware or kernel-driver defect. GPU support is an optional
upgrade and does not block the accepted CPU-only Phase 4 entry route.

No GPU package installation is authorized by this record.

## Explicit gaps

- Memory module topology requires a separately authorized privileged capture.
- Physical power supply, cooling assembly and ambient state require human observation.
- The Phase 3 CPU FP32 Policy Package is present at
  `/home/hepintel/physical_ai_os_artifacts/phase4_entry/policy_package_v2_9`; all eight selected
  files passed independent target-side SHA-256 verification. This proves transfer identity only.
- The artifact destination is writable and recorded, but remains an entry path rather than an
  execution authorization.
- CPU frequency, utilization, temperature and power sampling synchronization are not yet designed.
- Eleven pending OS updates were reported at login; they were not listed, installed or treated as
  part of the baseline.

## Entry impact

- Hardware identity: sufficient to name the CPU guard, but not yet complete for the full entry gate.
- Software identity: sufficient to trigger VM1 version-drift review.
- GPU: explicitly unavailable in the current userspace baseline and outside CPU-only qualification.
- Phase 4 execution: remains unauthorized.
