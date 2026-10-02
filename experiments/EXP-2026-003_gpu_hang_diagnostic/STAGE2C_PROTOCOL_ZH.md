# EXP-2026-003 GPU 挂起诊断 — Stage 2C 协议

协议编号：`EXP-2026-003-STAGE2C-PROC-THREAD-SNAPSHOT-V1`

状态：`CLOSED_AFTER_ROUND1__ROUNDS2_AND3_PROHIBITED`

分类：`EXPLORATORY_DIAGNOSTIC`

本协议不属于 GPU.0 资格测试，不改变 `GPU.0 CLOSED_NOT_ADMITTED`，也不启动 Phase 4。

## 1. 已知事实

Stage 2B 已得到稳定边界证据：

```text
H = 3,884
R = 3,884
E = 3,885
```

这支持：worker 进入第 3,885 次同步 `request.infer(inputs)`，但没有在15秒 watchdog 窗口内返回到 Python。

这仍然不能说明 infer 内部的 Runtime、Plugin、user-mode compute runtime、i915、firmware 或 GPU hardware 中哪一层是根因。

## 2. Stage 2C 要回答的唯一问题

当相同 infer-not-returned 症状再次发生、且 worker 尚未被 SIGTERM 回收时，Linux `/proc` 能观察到主线程和其他线程处于什么运行/等待状态？

本阶段只增加一次 timeout 后的进程/线程快照，不启用 strace、gdb、driver debug key 或持续性能采样。

## 3. 控制与单一新变量

### 控制路径

沿用冻结的 Stage 2B worker 和历史 supervisor：

- Stage 2B worker SHA-256：`7093c14a6b6eeed5fb3aa234a6e05c96b89d1e1039c661872e028490377f5672`；
- infer 前后共享计数器继续存在，用于确认新事件仍属于 `HANG_INFER_ENTERED_NOT_RETURNED`；
- 模型、输入、FP32、LATENCY、warmup、correctness、Queue heartbeat、telemetry 和 watchdog 参数不变。

### 唯一新增观察机制

当历史 supervisor 已判定 watchdog timeout 后：

```text
watchdog timeout
→ 启动一次有界 /proc snapshot helper
→ helper 完成或超时
→ 执行原 SIGTERM/SIGKILL 恢复
```

正常推理期间不读取 `/proc`，不轮询线程，不增加 worker 热路径操作。

## 4. 为什么选择 `/proc` 快照

- 它在故障已经出现后才运行，不改变正常 infer 调用的每次执行路径；
- 不需要修改驱动、内核、OpenVINO 或 GPU plugin；
- 可以 best-effort 观察主线程和其他线程的状态、等待点与当前系统调用；
- 比从一开始持续运行 strace 的扰动更小；
- 即使部分字段因权限不可读，也能明确记录 `UNAVAILABLE`，而不是猜测。

## 5. 快照内容

进程级：

- `/proc/<pid>/status`
- `/proc/<pid>/stat`
- `/proc/<pid>/wchan`
- `/proc/<pid>/syscall`
- `/proc/<pid>/sched`
- `/proc/<pid>/maps` 只记录 SHA-256 和映射摘要，不默认保存完整路径清单

线程级，对 `/proc/<pid>/task/<tid>/` 中每个当时可见线程记录：

- `tid`
- `comm`
- `status`
- `stat`
- `wchan`
- `syscall`
- `stack`（best-effort；权限拒绝必须保留为 `UNAVAILABLE`）

同时记录：

- snapshot helper 开始/结束时间；
- 目标 PID；
- 线程数；
- 每个字段的读取状态与错误；
- helper 是否在预算内完成。

## 6. 有界恢复要求

- snapshot helper 总预算：2秒。
- helper 在独立进程中运行；超时后由 supervisor 终止 helper。
- 无论快照成功、部分成功或超时，都必须继续执行原 worker 恢复。
- 相比 Stage 2B，SIGTERM 最多延后2秒；这个恢复延迟变化必须写入结果。
- 不允许因为某个 `/proc` 文件不可读而无限等待或跳过 worker 回收。

## 7. 两次快照还是一次快照

Stage 2C V1 只采集一次线程快照。

理由：本阶段首先验证能否在恢复预算内取得可解释的 OS-visible state。连续采样会新增时间维度和更多观测扰动，应作为未来独立变量，而不是混入 V1。

## 8. 结果分类

必须先保持 Stage 2B 边界分类，再增加 `/proc` 证据质量分类。

### Infer 边界

- `HANG_INFER_ENTERED_NOT_RETURNED`
- `HANG_AFTER_INFER_RETURN_BEFORE_HEARTBEAT`
- `HANG_AFTER_HEARTBEAT_BEFORE_NEXT_INFER`
- `BOUNDARY_EVIDENCE_INCONSISTENT`
- `NO_HANG_REPRODUCED_5M_COMPLETE`

### `/proc` 快照质量

- `PROC_SNAPSHOT_COMPLETE_WITHIN_BUDGET`
- `PROC_SNAPSHOT_PARTIAL_WITHIN_BUDGET`
- `PROC_SNAPSHOT_TIMEOUT`
- `PROC_SNAPSHOT_FAILED`
- `PROC_SNAPSHOT_NOT_TRIGGERED_NO_HANG`

不得把 `wchan`、某个 syscall 编号或线程状态直接命名为根因。

## 9. 每类证据能支持什么

### 主线程 `wchan` 是 futex/等待函数

可以说：快照时主线程在内核可见的等待点。

不能说：等待对象是谁持有、为什么没有被唤醒，或者驱动必然死锁。

### 主线程 `wchan` 为 `0` 或显示 running

可以说：快照没有观察到可命名的内核睡眠等待点。

不能说：GPU 正常、线程在有效计算，或者用户态一定在自旋。

### `syscall` 可读

可以记录快照时的系统调用编号和参数，之后依据当前架构的系统调用表解释。

不能仅凭一次系统调用快照证明长期阻塞位置或因果关系。

### `stack` 不可读

只能说：该字段因权限或接口限制不可用。

不能说：线程没有内核栈，或没有发生内核等待。

### 多个线程状态

可以描述快照时哪些线程 running/sleeping、各自 `wchan` 和 syscall。

不能仅凭线程数量或某个线程名称确定 OpenVINO/driver 内部所有权。

## 10. 重复与停止规则

- 最多三次，每次五分钟，每次由人单独启动并先做新预检。
- 任意一次同时得到：
  - 一致的 `HANG_INFER_ENTERED_NOT_RETURNED`；以及
  - `COMPLETE` 或 `PARTIAL_WITHIN_BUDGET` 的 `/proc` 快照；
  立即停止剩余次数并进入 Review。
- 如果发生 hang 但 helper timeout/failed：立即停止，先修正快照机制，不继续 GPU 尝试。
- 如果 infer 边界证据不一致：立即停止。
- 三次均未复现：停止，以 `INCONCLUSIVE_EVENT_DID_NOT_RECUR` 关闭。
- 禁止第四次。
- 任何结果均不恢复 GPU.0 准入。

## 11. 实现审计

- 不修改 Phase 3 历史脚本。
- 不修改冻结的 Stage 2B worker。
- 通过包装 historical `stop_worker`，在原恢复函数之前插入一次有界 helper；原恢复函数仍负责 SIGTERM/SIGKILL。
- helper 必须先在普通 mock 子进程上验证 complete、partial、timeout 和 target-exited 情形。
- 保存包装器差异、所有冻结哈希和 mock Review。
- 在 mock 与静态检查完成前，runner 必须拒绝真实 GPU 执行。

## 12. Stage 2C 之后的决策

如果取得可解释快照，只能据此选择下一条更窄的研究路径，例如：

- 主线程处于某个系统调用：评估是否值得进行一次有界 syscall trace；
- 主线程处于 futex：评估线程所有权和等待关系的专门实验；
- 主线程没有可见内核等待：评估官方 Runtime/Plugin 诊断或用户态采样；
- `/proc` 证据不足：评估安装/授权更强诊断工具的成本与风险。

每次只选择一个新的观察机制。

Human owner 于 2026-09-24 通过证据边界与有界恢复检查，允许进入实现和无 GPU mock；真实 GPU 执行仍需实现审计后单独接受。

在真实 Round 1 之前，实现和无 GPU mock 已完成。`STAGE2C_MOCK_REVIEW.md` 记录了 complete、partial、target-exited、timeout、helper-failed 与普通子进程 `/proc` 冒烟测试；`STAGE2C_FROZEN_MANIFEST.json` 冻结了真实执行使用的 baseline、worker、helper、runner 和 preflight 哈希。

真实 Round 1 `stage2c_r1_20260924_02` 已复现 `HANG_INFER_ENTERED_NOT_RETURNED` 并取得 `PROC_SNAPSHOT_PARTIAL_WITHIN_BUDGET`。按照第 10 节停止规则，Stage 2C 已关闭，Rounds 2 和 3 禁止执行。结论和证据边界见 `STAGE2C_ROUND1_REVIEW.md` 与 `STAGE2C_CLOSURE.md`。

## 13. 人工 Review 问题

1. 为什么 `/proc` 快照只在 watchdog timeout 后执行，对正常 infer 热路径的扰动更小？
2. 为什么看到 futex 也不能直接说“驱动死锁”？
3. 为什么 helper 超时后必须先回收 worker，而不是继续等待更多证据？
4. 为什么 Stage 2C V1 只拍一次快照，不连续采样？
