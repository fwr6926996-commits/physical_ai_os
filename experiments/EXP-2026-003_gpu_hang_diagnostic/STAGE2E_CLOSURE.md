# EXP-2026-003 Stage 2E Closure

## Status

`CLOSED AFTER ONE APPROVED ATTEMPT — NO RETRY`

## Result

Stage 2E-A 复现 `HANG_INFER_ENTERED_NOT_RETURNED`，并取得完整的主线程 PC、module mapping
和稳定 `libigdrcl.so` offset `0x4008c6`。

该 PC 位于 `tpause` 后的向后跳转；周围指令构成包含 `pause/tpause`、predicate、时间检查和
`sched_yield` 的用户态等待循环。其语义与精确版本 Intel compute-runtime 的 WaitUtils
等待实现高度一致。

Stage 2D 与 Stage 2E 的顶部九个 `libigdrcl.so` frames 只有一个固定 ASLR 平移差，支持两次
事件位于同一内部调用链。

## Evidence boundary

现在已经从“infer 内部不返回”推进到“同一 native 调用链中的用户态 completion-style wait
循环”。这仍然是等待位置，不是导致等待条件永远不满足的根因。

## Route

下一步优先把 Build ID、offset、指令语义和两次相同栈链补充到 Intel compute-runtime
issue #1012，并询问：

1. offset `0x4008c6` 在 Build ID `58cc...8e35` 中对应的内部函数；
2. frames `0x3cd8b9 → 0x33082e → 0x4c5043 ...` 对应的等待/提交调用链；
3. 该等待循环正在检查哪个 completion/tag 条件；
4. 上游希望下一步采集哪一种 GPU/kernel-side 有界证据。

在上游反馈或匹配 symbols 给出新的可判别问题前，不再进行 GPU 实验。

## Gate

- GPU.0：`CLOSED_NOT_ADMITTED`
- CPU FP32：继续作为唯一 admitted backend
- Phase 3：`PARTIAL PASS — CPU FP32 ONLY`
- Phase 4：不因本实验自动启动

