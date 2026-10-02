# Phase 3 Independent Learning Verification

Verification ID: `P3-V2.9-LEARNING-VERIFY-001`

Opened: `2026-10-01`

Owner: human

Mode: `INDEPENDENT_EXPLANATION_WITH_EVIDENCE`

Status: `ACCEPTED`

Accepted: `2026-10-01`

Human decision: `ACCEPT`

## Purpose

Verify learning separately from experimental completion and backend admission. This record did not
change `phase3_final_gate.json` until all required capabilities had sufficient evidence and the human
explicitly accepted the final result. Those conditions were completed on `2026-10-01`.

Earlier guided answers and completed commands are supporting learning history, but they are not
silently treated as the final independent response.

## Assessment method

- The human answers in their own words.
- Exact filenames and numeric values may be looked up; the reasoning must be independently explained.
- Codex may ask a clarification when an answer is ambiguous, but does not replace the human answer.
- Each item is assessed as `PASS`, `PARTIAL`, or `NOT_YET` with a short evidence boundary.
- No GPU execution, Phase 4 action or robot motion is part of this verification.

## Verification items

### Q1 — Admission reasoning

Explain why CPU FP32 is admitted while GPU.0 FP32 is not, even though GPU.0 passed correctness and
was faster in short runs. State which evidence supports each part and what the evidence does not
prove.

Status: `PASS`

Human response:

> 因为 CPU 通过了稳定性测试。我们分别对两个后端进行了三十分钟的稳定性测试，一个通过
> 一个不通过。不能证明在真正的 edge 端去使用的时候就是这样的。
>
> 澄清：两次提前停止能够证明 GPU.0 的确不通过稳定性测试，但是不能证明内部原因到底
> 是什么，更不能把结论迁移到未来的 DK-2500 部署。

Assessment: `PASS`. The combined response identifies stability—not correctness or short-run speed—as
the decisive admission difference. It correctly distinguishes a 30-minute target from GPU.0's two
early formal failures, limits the conclusion to the frozen 255H environment and protocol, and does
not promote failure evidence into a root-cause or DK-2500 claim.

### Q2 — Runtime contract and interfaces

Identify the active runtime device, precision, performance hint, model inputs and output. Identify
the active configuration and the principal evidence/report files you would inspect before changing
the backend.

Status: `PASS`

Human response:

> 回答不出来，我也不知道怎么去仓库查。
>
> 检索后重答：设备后端、量化数据类型；`performance_hint` 不知道。输入是 state 的关节
> 数据和 wrist 的图像数据，输出是 action 的动作数据。应该检查 correctness 和 stability
> 文件；两类证据不知道。
>
> 第二次重答：`device=CPU`、`precision=f32`、`performance_hint=LATENCY`；输入为
> `state float32[1,6]` 和 `wrist_image float32[1,3,480,640]`，输出为
> `action_chunk float32[1,100,6]`。改后端前检查 `PHASE3_FINAL_REPORT.md`；重点检查
> correctness 和 stability 两类证据。第二个源文件及“改配置为何不等于准入”尚未回答。
>
> 最终澄清：另一个文件是 `active_runtime_config.yaml`。手动把设备改成 GPU.0 不能使其
> 自动准入，因为 GPU.0 并没有完成稳定性测试。

Assessment: The runtime contract has not yet been independently identified. The immediate Mystery
Debt is repository evidence retrieval rather than memorization. Complete a focused `rg`/`sed`
lookup exercise using the active configuration and final report, then retry Q2.

Learning exercise: `COMPLETED`. The human used `grep -nE` to locate the runtime contract in
`active_runtime_config.yaml` and the admission/correctness/stability evidence in
`PHASE3_FINAL_REPORT.md`. The initial `rg` attempt also established how zsh command correction can
silently substitute a different command when a tool is unavailable.

Clarification assessment: The human understands the semantic roles of state, wrist image and action
output, but has not yet stated the exact frozen values/shapes. The response also swaps evidence types
with source files. `f32` is floating-point precision in this contract, not INT8 quantization;
`LATENCY` is an OpenVINO optimization hint, not a real-time deadline guarantee. Retry after this
distinction is explained.

Second clarification assessment: Exact runtime and tensor-contract values are now correct, and the
correctness/stability evidence categories are correctly identified. The remaining source is
`active_runtime_config.yaml`. One final explanation is required to distinguish editing a declared
configuration from earning backend admission through evidence.

Final assessment: `PASS`. The human identified the active runtime and tensor interfaces, located the
active configuration and final evidence report, distinguished correctness from stability evidence,
and explained that changing a configuration declaration cannot replace a missing admission gate.

### Q3 — Meaningful modification

Choose one meaningful parameter from the stability or diagnostic path—for example watchdog timeout,
device, precision or maximum duration. Explain what changing it would test, what else must remain
frozen, and why the resulting run could or could not be compared with earlier evidence.

Status: `PASS`

Human response:

> 其他参数觉得能够回答，但不清楚把 watchdog 从 15 秒改为 30 秒意味着什么。
>
> 澄清回答：验证这个延迟究竟是不是在 15–30 秒区间；不能验证内部到底是什么原因；
> 修改后的结果不能直接替代原稳定性结果，因为条件已经改变。
>
> 单变量补充：precision、device 和测试时长都不能变。

Assessment: `PARTIAL — CLARIFICATION REQUIRED`. The human correctly treats the watchdog as a changed
observation/recovery boundary, identifies the 15-to-30-second return window it can discriminate,
rejects root-cause attribution and recognizes that the changed condition cannot replace the original
stability result. The response still needs to identify the principal variables that must remain
frozen so watchdog duration is the only change.

Final assessment: `PASS`. The human explained the discriminating question and evidence ceiling,
recognized the changed recovery/observation condition prevents direct replacement of the original
gate, and identified device, precision and maximum test duration as frozen controls. Model/input and
software/implementation identities remain manifest-enforced controls in an actual run.

### Q4 — Reproduction path

Describe the minimum path for reproducing a backend qualification or a bounded hang diagnostic:
preflight, frozen identities, execution boundary, evidence outputs, recovery and stop rule. Explain
why a successful short run is not enough to readmit GPU.0.

Status: `PASS`

Human response:

> 不清楚。
>
> 外部恢复初答：挂起后恢复会破坏进程的对照性，必须通过 supervisor 进行单独恢复。
>
> 流程重答：运行前确认 device、precision、OpenVINO/driver 版本、模型与输入 hash、
> worker/runner hash；运行中观察 infer 的进入和返回；超时后保存 stack、module mapping、
> 进程/线程状态等协议要求的证据；由 supervisor 恢复 worker；按照预定规则，在问题已
> 解决、达到最大轮次或触发失败条件时停止。
>
> 短跑限制：一次没有挂起的成功短跑不能否认之前的稳定性问题，不能用短时或偶发结果
> 抹掉有效失败。

Assessment: The bounded reproduction path is not yet independently explainable. The Mystery Debt is
the relationship among identity preflight, call-boundary events, bounded evidence capture,
out-of-process recovery and a precommitted stop rule. Complete a focused walkthrough and retry Q4.

External-recovery clarification: Separate supervision does preserve a cleaner observation boundary,
but the primary requirement is liveness: a worker blocked inside the native `infer()` call cannot
advance to its own later Python recovery code. The supervisor remains executable and can capture
bounded evidence, signal the exact worker PID and preserve the result.

External-recovery check: `PASS`. The human confirmed that a worker blocked inside `infer()` cannot
execute the next Python line and that the supervisor, not the worker, sends SIGTERM.

Reproduction-path retry: `PARTIAL — ONE ITEM REMAINS`. Identity freeze, enter/return observation,
bounded evidence capture, supervisor recovery and precommitted stopping are all correctly stated.
The final response must still explain why a successful short run cannot readmit GPU.0.

Final assessment: `PASS`. The human independently reconstructed the bounded reproduction chain,
understood why recovery must remain outside the blocked worker, identified precommitted stop
conditions, and correctly refused to treat one short non-reproduction as evidence that invalidates
prior failures or satisfies the stability gate.

### Q5 — Debugging route and evidence ceiling

Starting from `infer_entered_not_returned`, explain how the investigation narrowed the boundary and
what Stage 2E finally established. Then state the strongest conclusion supported and at least two
root-cause claims that remain unsupported.

Status: `PASS`

Human response:

> `infer_entered_not_returned` 把问题定位到单次执行内部；后续 GDB/module mapping/Stage 2E
> 的推进忘记了；当前最强结论和不能证明的根因判断不清楚。
>
> 检索后重答：知道主线程位于包含 `pause/tpause/sched_yield` 的用户态等待循环，但是不
> 知道为什么等不到。在这个位置等待，不能说明问题由这个位置产生。另一个不能确定的
> 根因尚不清楚。
>
> Completion-tag 初答：认为 runtime 不能一直等待，因为 watchdog 会监视并叫停。
>
> 最终澄清：watchdog 触发后 Worker 被外部终止，`infer()` 并没有正常返回；watchdog
> 不能证明 completion tag 为什么没有更新，因为它只在 runtime 外部监管进展。

Assessment: The initial synchronous-call boundary is understood, but native localization and the
evidence ceiling are not yet independently explainable. Complete a repository evidence-retrieval
exercise from the dated Review–Route–Feedback addendum and retry Q5. Exact addresses are lookup
data; the required capability is explaining the progression and refusing unsupported causality.

Retrieval retry: `PARTIAL — ONE ITEM REMAINS`. The human now identifies the user-space wait-loop
boundary and correctly distinguishes an observed waiting location from the component that created
the unmet condition. One concrete competing root-cause explanation is still required.

Completion-tag clarification: The response conflates the internal runtime wait condition with the
external supervisor recovery bound. The runtime may continue waiting because it has not observed the
expected completion tag; the watchdog does not satisfy that condition or make `infer()` return. It
captures evidence and terminates the blocked worker from outside after the no-progress threshold.

Final assessment: `PASS`. The human identified the strongest observed boundary—a repeated native
`libigdrcl.so` call chain and user-space completion-style wait—without treating the waiting location
as the originating fault. They also distinguished an uncompleted GPU task from a completion-tag
publication/visibility failure and separated runtime waiting from external watchdog recovery.

### Q6 — Safety boundary

Explain why CPU correctness plus a 30-minute offline stability pass does not establish real-time
control behavior or physical robot safety. Name the kinds of later evidence that would be required.

Status: `PASS`

Human response:

> 这只证明推理稳定性。实际物理世界中，延迟带来的问题不能直接判断；至少真机推理时
> 不能发生碰撞。
>
> 澄清：Real-Time 至少测端到端控制周期延迟；Safety 至少验证急停。必须通过底层安全
> 规则确保 safety，并以足够频率/重复次数覆盖实际情况，不能用一次未碰撞作为证明。

Assessment: The response correctly limits Phase 3 evidence to inference stability and recognizes that
latency and physical interaction create separate risks. It still needs one measurable real-time
control acceptance item and one repeatable safety mechanism/test beyond merely observing no collision
in a run.

Final assessment: `PASS`. The human selected end-to-end control-cycle latency as a measurable
real-time item, emergency stop as an independent physical safety mechanism, and recognized that
safety requires lower-level rules plus repeated, representative verification rather than one
collision-free observation.

## Verification summary

| Item | Result |
|---|---|
| Q1 Admission reasoning | PASS |
| Q2 Runtime contract and interfaces | PASS |
| Q3 Meaningful modification | PASS |
| Q4 Reproduction path | PASS |
| Q5 Debugging route and evidence ceiling | PASS |
| Q6 Safety boundary | PASS |

All required capabilities have sufficient evidence. Repository lookup and the distinction between
internal runtime waiting and external supervisor recovery required focused remediation during the
verification; both were rechecked successfully.

Final Phase 3 learning acceptance was explicitly accepted by the human on `2026-10-01`. The
engineering gate remains `PARTIAL_PASS_CPU_FP32_ONLY`; GPU.0 remains not admitted and Phase 4 remains
not started.

## Completion rule

All six items require `PASS`. Any `PARTIAL` item receives one focused clarification. If a capability
remains `NOT_YET`, record it as Mystery Debt and perform a separate learning exercise before retrying
that item.

After all items pass, the human still owns the final acceptance decision. Only then may the Phase 3
learning fields and final acceptance status be updated, while preserving the engineering gate as
`PARTIAL_PASS_CPU_FP32_ONLY`.
