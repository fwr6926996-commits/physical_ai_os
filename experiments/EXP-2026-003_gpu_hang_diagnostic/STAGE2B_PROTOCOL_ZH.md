# EXP-2026-003 GPU 挂起诊断 — Stage 2B 协议

协议编号：`EXP-2026-003-STAGE2B-INFER-BOUNDARY-SHARED-STATE-V1`

状态：`CLOSED_AFTER_ROUND1__HANG_INFER_ENTERED_NOT_RETURNED__FURTHER_STAGE2B_RUNS_PROHIBITED`

分类：`EXPLORATORY_DIAGNOSTIC`

本协议不属于 GPU.0 资格测试，不改变 `GPU.0 CLOSED_NOT_ADMITTED`，也不启动 Phase 4。

## 1. Stage 2B 要回答的唯一问题

当历史“心跳停止”症状再次出现时，最后进入的 `request.infer(inputs)` 是否已经返回？

本阶段不尝试直接回答 OpenVINO Runtime、Intel GPU Plugin、i915 驱动或 GPU 硬件中的哪一层是根因。

## 2. 为什么现在可以进入 Stage 2B

Stage 2A 使用未修改的历史 worker 路径进行三次独立五分钟尝试：

- Round 1：未复现；
- Round 2：未复现；
- Round 3：84.680417 秒后复现，watchdog 恢复。

因此，当前环境下已经恢复了间歇性故障信号。Stage 2B 不再需要证明“问题是否还存在”，而是把观察边界从“heartbeat 没到”缩小到同步 infer 调用边界。

## 3. A/B 定义

### A：当前控制证据

Stage 2A 是冻结控制路径：历史 worker、Queue heartbeat、输出复制、correctness 检查和父进程 watchdog 均保持原样。当前控制序列为三次尝试中一次复现。

Stage 2A 已关闭，不为了 Stage 2B 再追加 A 组运行。A 组样本只用于证明当前历史路径仍可复现，不用于估计可靠故障率。

### B：最小调用边界观察

在 Stage 2A worker 的每次同步推理周围只增加一个共享状态观察机制：

```text
shared_enter_sequence = N
request.infer(inputs)
shared_return_sequence = N
```

父进程正常运行期间不轮询这两个值。原 watchdog timeout 和恢复流程保持不变；worker 被有界回收后，包装器读取两次共享值并形成稳定快照。

## 4. 为什么选择共享计数器

Stage 1 在每次推理前后通过 Pipe 发送事件，这会产生序列化、IPC 和父进程事件处理开销。Stage 2B 改用两个由单一 worker 写入的无锁共享整数：

- 每次推理只增加两次共享内存写入；
- 不增加每次推理的 Queue/Pipe 消息；
- 不改变原 heartbeat 内容和频率；
- 不改变输出获取、correctness 检查或原 Queue heartbeat 路径；
- 包装器只在历史运行函数返回后读取。

共享写入仍然会扰动时序，因此“低扰动”不等于“零扰动”。如果 B 组不复现，不能说计数器修复了问题。

## 5. 计数范围

序号覆盖 worker 中的全部同步推理：

- initial correctness inference；
- 10 次 warmup；
- measurement inference。

因此，在固定 warmup 10 的 measurement 阶段：

```text
measurement iteration M 对应 infer sequence M + 11
```

这个换算必须由结果脚本自动完成，不能依赖人工心算形成正式证据。

## 6. timeout 时的解释规则

设：

- `E` = 稳定读取的最后 enter sequence；
- `R` = 稳定读取的最后 return sequence；
- `H` = 从父进程收到的最后 heartbeat 对应的 infer sequence。

### 情形 1：`E = R + 1`

```text
infer_enter(N) 已记录
infer_return(N) 未记录
```

支持的结论：第 N 次同步 `request.infer(inputs)` 在 watchdog 窗口内没有返回。

不能支持：infer 内部哪一层是根因。

### 情形 2：`E = R` 且 `R > H`

支持的结论：最后一次 infer 已经返回，失去进展发生在 infer 返回之后、下一次 heartbeat 被父进程确认之前。

仍包含：输出 tensor 获取/复制、correctness 计算、Queue publication 或 Queue delivery。

### 情形 3：`E = R = H`

支持的结论：最后一次 infer 和 heartbeat 已完成，失去进展发生在该 heartbeat 与下一次 infer enter 之间，或者父进程观察存在边界竞争。

### 情形 4：其他关系

例如 `R > E`、`E - R > 1`、两次快照不稳定，统一分类为：

`BOUNDARY_EVIDENCE_INCONSISTENT`

不得强行解释根因。

## 7. 共享状态可靠性边界

- 仅 worker 写；包装器在 worker 正常退出或被 watchdog 回收后读。
- 使用对齐的 64-bit 无锁共享整数，以减少锁和 IPC 扰动。
- 父进程间隔短时间读取两次；只有两次值相同才称为稳定快照。
- Python/multiprocessing 不为所有平台保证任意无锁复合操作的原子性；本协议只依赖单个对齐整数值，并仍保留 `INCONSISTENT` 分类。
- 共享计数器证据只能定位调用边界，不能观察原生调用内部状态。

## 8. 保持不变的因素

- GPU.0 Intel Arc iGPU；
- FP32 与 LATENCY；
- 冻结模型、参考输入输出和数值容差；
- OpenVINO、kernel、driver 和 plugin；
- initial/warmup/measurement 顺序；
- warmup 10；
- 每次 measurement 最长5分钟；
- stall 15秒、startup 60秒；
- telemetry 5秒、window 60秒；
- 原输出复制、correctness 检查、Queue heartbeat、父进程遥测和恢复策略；
- 每次运行前独立环境预检。

## 9. 实现审计要求

- 不修改 Phase 3 历史脚本。
- 从已验证哈希的历史脚本派生 Stage 2B 文件。
- 保存机器可读 patch/diff，证明 worker 热路径只增加 enter/return 共享写入。
- 任何其他必要改动必须单独列出并解释为什么不改变 inference 行为。
- 静态检查和 mock timeout 测试必须在真实 GPU 运行前完成。
- mock 测试只验证计数器解释和 watchdog，不算 Stage 2B GPU 尝试。

Human owner 于 2026-09-24 通过证据逻辑检查并允许进入实现与 mock 阶段；真实 GPU 执行仍需实现审计后单独放行。

### 实现与 mock 记录

- 历史 baseline SHA-256：`4fae4ce71896db4eafe01932b89076c46d11f401f6f64ad2fa3b78ae650cbab7`。
- 冻结 Stage 2B worker SHA-256：`7093c14a6b6eeed5fb3aa234a6e05c96b89d1e1039c661872e028490377f5672`。
- worker 热路径差异：仅函数增加两个共享参数、维护 infer sequence、并在 initial/warmup/measurement 的 infer 前后写 enter/return。
- 无 GPU mock：五种分类全部通过。
- spawn/partial 接线 mock：通过，历史 supervisor 形状的三个参数保持原位，两个共享值通过预绑定传入。
- 真实 GPU 尝试数：0。

Human owner 于 2026-09-24 接受真实执行边界：最多三次、每次五分钟、逐次预检与 Review；首次获得一致挂起边界或任何不一致证据即停止；三次不复现则以 inconclusive 关闭；所有结果均不恢复 GPU.0 准入。

### 执行记录

- Round 1：`stage2b_r1_20260924_01`。
- 分类：`HANG_INFER_ENTERED_NOT_RETURNED`。
- 最后确认 heartbeat infer sequence：3,884。
- 最后 return sequence：3,884。
- 最后 enter sequence：3,885。
- 两次 post-recovery 共享快照一致。
- watchdog：15.089199 秒无 heartbeat 后触发，SIGTERM 恢复。
- 决策：首次获得一致挂起边界，停止规则触发；Round 2、3 禁止。
- GPU.0 仍为 `CLOSED_NOT_ADMITTED`。

## 10. B 组重复与停止规则

- 最多三次，每次五分钟，每次由人单独启动。
- 每次先生成新的环境预检，并在运行后单独 Review。
- 任意一次复现并获得一致的稳定边界快照：立即停止剩余尝试。
- 任意一次产生 `BOUNDARY_EVIDENCE_INCONSISTENT`：停止，先修正观察设计，不继续 GPU 尝试。
- 三次均未复现：停止，不运行第四次；结论为 `INCONCLUSIVE_OBSERVATION_MAY_HAVE_PERTURBED_OR_EVENT_DID_NOT_RECUR`。
- 不以任何成功运行恢复 GPU.0 准入。

最大 B 组主动测量时间为15分钟。

## 11. B 组结果分类

- `HANG_INFER_ENTERED_NOT_RETURNED`
- `HANG_AFTER_INFER_RETURN_BEFORE_HEARTBEAT`
- `HANG_AFTER_HEARTBEAT_BEFORE_NEXT_INFER`
- `BOUNDARY_EVIDENCE_INCONSISTENT`
- `NO_HANG_REPRODUCED_5M_COMPLETE`
- `CORRECTNESS_OR_NONFINITE_FAILURE`
- `STARTUP_OR_ENVIRONMENT_FAILURE`
- `UNEXPECTED_OR_INCOMPLETE`

这些都是诊断分类，不是部署 PASS。

## 12. 如果定位到 infer 未返回，下一步是什么

只有得到 `HANG_INFER_ENTERED_NOT_RETURNED` 后，才允许设计 Stage 2C，在以下层中一次选择一个新的观察边界：

- Python/native 调用边界；
- OpenVINO/Plugin 可用的官方诊断信息；
- 进程/线程等待状态；
- 系统调用或内核 GPU 报告。

Stage 2B 本身不得把“infer 未返回”改写成“驱动故障”或“GPU 硬件故障”。

## 13. 人工 Review 问题

1. `E = R + 1` 能证明什么，不能证明什么？
2. `E = R` 且 `R > H` 为什么说明 infer 已经返回？
3. 为什么 B 组三次不复现仍不能说计数器解决了挂起？
4. 为什么这次不再通过 Pipe 逐次发送 enter/return？
