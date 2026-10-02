# Submitted follow-up for Intel compute-runtime issue #1012

Status: `SUBMITTED`  
Submitted: 2026-10-01 01:49 Asia/Shanghai  
Issue: https://github.com/intel/compute-runtime/issues/1012  
Submission account: `fwr6926996-commits`

Stage 2E-A reproduced the same failure in one approved bounded attempt and converted the stopped-time
main-thread PC to a stable module offset.

Environment and binary identity are unchanged from the original report:

- `intel-opencl-icd 25.18.33578.77-1146~24.04`
- `libigdrcl.so` Build ID: `58ccca242c62c0629c06940ee3d7b8a40b298e35`
- `libigdrcl.so` SHA-256: `d43af828e1acfcce4a2c042167ecacb270e9356fa55a3a557f18cd55b79540da`
- OpenVINO: `2026.3.1-22476-759c5a6ab8c-releases/2026/3`
- Intel Arrow Lake-P iGPU, Linux `7.0.0-31-generic`, i915

The failure occurred after 6,748 correct measured inferences (plus initial inference and 10 warmups):

```text
last infer return sequence = 6759
next infer enter sequence  = 6760
watchdog timeout           = 15.07 s
worker CPU                 = 99.9%
threads                    = 37
recovery                   = SIGTERM
```

The main thread was selected by Linux LWP equal to the worker PID. GDB captured:

```text
PC                  = 0x74aeb8e008c6
mapping_start       = 0x74aeb8a00000
mapping_file_offset = 0x0
stable module offset = 0x4008c6
module              = /usr/lib/x86_64-linux-gnu/intel-opencl/libigdrcl.so
```

The top nine stable `libigdrcl.so` offsets were:

```text
0x4008c6
0x3cd8b9
0x33082e
0x4c5043
0x1581ee
0x1c4f6f
0x13c6cd
0x10b3dd
0x0d2c2b
```

All nine Stage 2E absolute frame addresses differ from the earlier Stage 2D capture by exactly the same
ASLR delta, so both failures were observed in the same internal call chain.

Disassembly around the top PC is:

```text
0x4008c2  tpause %ecx
0x4008c6  jmp    0x40073d
```

The surrounding loop includes `pause`, predicate calls, time checks, `tpause`, and `sched_yield`.
Its instruction-level behavior is consistent with the wait utilities in the matching public source,
but the installed library is stripped, so we are not claiming a symbolized function identity or root cause.

Could you please help identify:

1. the internal function/call chain for these offsets in Build ID `58cc...8e35`;
2. which completion/tag condition this loop is waiting for;
3. whether this build has a known issue that can leave that condition unsatisfied; and
4. the next lowest-perturbation GPU/kernel-side evidence you would recommend?

We have closed this local stage after the single approved attempt and will not rerun without a new,
specific diagnostic question.
