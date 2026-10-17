# Phase 4 Thermal D2-IDLE Implementation and Mock Protocol

Template: `EXPERIMENT_PROTOCOL.md` version `0.1` (`TRIAL`)

## Identity

- Protocol ID: `P4-DK2500-THERMAL-D2-IDLE-MOCK-001`
- Protocol version: `0.1`
- Owner: human
- Reviewers: human owner and Codex
- Date frozen: `2026-10-14`
- Classification: `EXPLORATORY — NO-TARGET IMPLEMENTATION VALIDATION`
- Governing design: `PHASE4_THERMAL_D2_IDLE_DESIGN_REVIEW_20261014.md`
- Status: `FROZEN FOR LOCAL IMPLEMENTATION AND ARTIFICIAL-INPUT MOCK ONLY`
- Target authorization: `NONE`

## Question and decision

- Question: Does the proposed D2-IDLE sampler/Supervisor implementation correctly preserve and
  classify artificial timing, activity, counter, interface and thermal sequences while preventing
  unapproved target mode?
- Decision this result may support: engineering and learning review of implementation readiness for
  a later executable D2-IDLE protocol.
- Claims this check cannot support: DK-2500 connectivity, actual interface topology, idle behavior,
  throttle occurrence, temperature, timing, Stability, deployment, real-time or safety.

## Protected boundaries

- no SSH or other DK-2500 access;
- no target authorization file;
- no OpenVINO, model or deliberate load;
- no system, network, permission or package change;
- mock evidence is written only under the local repository evidence directory;
- production mode must fail before creating a run directory when authorization or key is missing;
- fixture mode must reject SSH key and authorization arguments.

## Accepted design constants

- pre-observation: `30 seconds`, seven samples and six CPU-busy windows;
- formal observation: `600 seconds`, 121 samples including the shared boundary sample;
- full sequence: 127 unique samples through approximately `630 seconds`;
- interval: `5 seconds`;
- watchdog: `15 seconds` without a complete line/event;
- startup allowance: `30 seconds`;
- thermal stop: any readable sensor `>= 100 C`;
- pre-observation average CPU busy: `<= 10%`;
- formal-observation average CPU busy: `<= 10%`;
- early contamination: three consecutive formal five-second windows each `> 20%`;
- maximum target attempts: one, with no automatic retry or reconnect.

## Frozen CPU-busy formula

For the aggregate `cpu` line in consecutive `/proc/stat` samples:

- accepted fields: `user`, `nice`, `system`, `idle`, `iowait`, `irq`, `softirq`, `steal`;
- `guest` and `guest_nice` are excluded because their time is already included in user/nice;
- `total = sum(accepted fields)`;
- `idle_all = idle + iowait`;
- `busy_percent = 100 * (delta_total - delta_idle_all) / delta_total`.

A missing field, negative component delta, `delta_total <= 0`, busy result outside `0..100`, or
counter reset is an evidence failure. `/proc/loadavg` is descriptive only.

## Implementation contract

### Target-side sampler source

- self-contained Python standard-library source;
- emits JSONL to stdout only;
- creates no target file;
- discovers an initial interface inventory and freezes it for the sequence;
- records target monotonic time before/after every sample, target UTC, boot ID, read duration,
  per-path throttle fields, temperatures, frequency paths, `/proc/stat`, `/proc/loadavg` and errors;
- schedules samples from the original monotonic deadline rather than accumulating sleep drift;
- emits an explicit terminal event on completion or a local stop classification.

The target-side source may exist locally for implementation review. This protocol does not
authorize streaming or executing it on DK-2500.

### Local Supervisor

- fixture mode consumes only an artificial JSONL sequence;
- production mode requires a future run-specific authorization matching protocol, run, target,
  timeout and exact code/protocol hashes before SSH or evidence-directory creation;
- preserves raw stdout/stderr and command identity;
- independently recomputes CPU busy, timing, sample counts, temperature maximum and every exact
  throttle-path delta;
- never sums repeated package paths;
- preserves partial evidence and returns a nonzero code for failure/contamination classifications;
- contains a bounded progress watchdog and no retry loop.

## Mock matrix

The no-target validator must cover at least:

1. complete 127-sample quiet sequence;
2. pre-observation average above `10%`;
3. three consecutive formal windows above `20%`;
4. complete formal sequence whose overall average exceeds `10%`;
5. temperature `>= 100 C` stop;
6. missing interface path after inventory freeze;
7. negative throttle-counter delta;
8. boot-ID change;
9. monotonic reversal;
10. sample-read duration reaching `5 seconds`;
11. malformed `/proc/stat` or nonpositive total delta;
12. production mode without authorization fails before evidence creation;
13. fixture mode rejects authorization or SSH arguments;
14. package paths remain separate and the result states summation was omitted.

## Evidence contract

Proposed local evidence:
`evidence/phase4_0_harness/thermal_d2_idle_mock_validation_20261014_01.json`

The evidence must record:

- protocol and implementation hashes;
- each mock case, return code, status and essential recomputed fields;
- `target_accessed: false` and `execution_authorized: false`;
- explicit interpretation limits;
- separate implementation Review after execution.

## Run and stop policy

- local mock validation may run once after implementation;
- no target attempt exists in this protocol;
- any unexpected SSH invocation, target access, target evidence directory or authorization record is
  a hard failure;
- implementation defects may be corrected and the local mock rerun only if every failed attempt is
  preserved or the failed run produced no designated evidence artifact;
- no mock result may be promoted into target evidence.

## Pre-run review

- [x] Human authorized implementation and artificial-input mock only.
- [x] Target access and target authorization are explicitly prohibited.
- [x] Timing, activity, thermal and path rules were accepted before mock results.
- [x] CPU-busy formula is frozen before implementation validation.
- [x] Required failure cases and prohibited claims are explicit.

## Deviations

None. No mock has run and no target access has occurred.
