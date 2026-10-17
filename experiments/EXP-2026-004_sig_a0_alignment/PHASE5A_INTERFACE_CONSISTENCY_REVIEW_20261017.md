# Phase 5A Interface Baseline Consistency Review

Review date: `2026-10-17`

Status: `READY_FOR_OWNER_REVIEW`

Scope: targeted comparison of the SIG-A0 interface baseline with the frozen L1 V2.9 execution book,
Architecture Audit Addendum 01 and Portability Addendum 02. No upstream research was repeated. No
source implementation, dependency installation, build, simulation or hardware operation occurred.

## Authority check

The three repository documents match their recorded SHA-256 values:

| Document | Result |
|---|---|
| L1 V2.9 execution book | PASS — `95cd404a72f0c03435b0728aa0bd169f78a6b782f9063a4b6659cbc953bec5ef` |
| Architecture Audit Addendum 01 | PASS — `eb34eedec544d8f327a321b9e4188055ffcd54aee4a44b7672cb5955e95e8091` |
| Portability Addendum 02 | PASS — `e3b4aea1b8cdcf425762fa980d4bc6189e109f726d9238bea6f1c146dc7551b6` |

## Finding matrix

| ID | Finding | Authority | Classification | Resolution |
|---|---|---|---|---|
| F1 | SIG-A0 used `DISABLED / READY / PERMITTED / FAULT / ESTOP` | V2.9 section 3.4 and state table freeze `DISARMED / ARMED / RUNNING / DEGRADED / FAULT / SAFE` | Non-intentional deviation | Restore the six frozen states and recovery semantics |
| F2 | `Observation` omitted state/assembly time, sensor/task/gripper/health and data-version semantics | V2.9 Observation table; Addendum 02 unified Observation contract | Incomplete field baseline | Restore the required logical fields without changing the frozen document |
| F3 | `PolicyOutput` omitted model version, action step, status and confidence semantics | V2.9 PolicyOutput table | Incomplete field baseline | Restore the missing fields; keep one-action Phase 5A restriction |
| F4 | `RuntimeMetrics` omitted the nine raw time points and summary evidence split | V2.9 timing and metrics tables | Incomplete evidence contract | Restore raw time points and define event records plus run summaries |
| F5 | Message-wide `clock_domain` did not satisfy Gate T0 per-time-field metadata | Addendum 01 Gate T0 | Gate mismatch | Define `ClockedTimestamp` with all five metadata items and contract version |
| F6 | `ControlCommand` was described before the permission boundary | V2.9 section 3.3 and Safety tables | Semantic ordering error | Make `ControlCommand` post-`SafetyFilter`; use internal `CommandCandidate` before it |
| F7 | Existing source-review and component dispositions remain sound | SIG-A0 fixed-source evidence | No change | Preserve all identities, license findings and dispositions |

## ADR decision

No finding is an intentional architecture change. The correction restores the approved architecture
to the governing baseline, so a new ADR is not required. If Owner Review instead chooses the
five-state safety model, removes a V2.9-required field or moves `ControlCommand` before
`SafetyFilter`, that choice becomes an Architecture Change and must stop here for a separate ADR.

## Review conclusion

`PASS_WITH_CORRECTION_PENDING_OWNER_REVIEW`

The proposed correction is sufficient to close the identified consistency gap without reopening
SIG-A0 source research. SIG-A0 remains `PASS — ARCHITECTURE REVIEW ONLY` for its upstream research
and component dispositions. The Phase 5A interface field freeze remains pending until this PR is
approved and merged. Phase 5A implementation remains separately authorized.
