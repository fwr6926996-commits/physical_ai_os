# EXP-2026-003 GPU 挂起诊断 — Stage 2 协议

协议编号：`EXP-2026-003-STAGE2-REPRODUCE-THEN-LOCALIZE-V1`

状态：`STAGE2A_CLOSED__HANG_REPRODUCED_IN_ROUND3__STAGE2B_DESIGN_ALLOWED`

分类：`EXPLORATORY_DIAGNOSTIC`

本协议不属于 Phase 3 第三轮资格测试，不改变 `GPU.0 CLOSED_NOT_ADMITTED`，也不启动 Phase 4。

## 1. 为什么不直接继续运行 Stage 1

Stage 1 一次完成 180 秒，但它相对历史失败脚本同时改变了多项因素：

- Queue 改为 Pipe；
- 每次推理增加 `infer_enter` 和 `infer_return` 两次消息；
- 取消父进程周期遥测；
- warmup 增加输出检查；
- 运行时长从 30 分钟变为 3 分钟。

因此，Stage 1 没有复现可能来自故障本身的间歇性，也可能与时序扰动有关。继续重复 Stage 1 不能区分这两种解释。

## 2. 总体决策树

```text
Stage 2A：当前环境还能复现历史失败路径吗？
├─ 复现一次 → 立即停止 2A，保存证据，设计 Stage 2B 单变量观察实验
└─ 三次均未复现 → 停止主动复现，转为长期 incident capture
```

Stage 2A 和 Stage 2B 不在同一次批准中执行。Stage 2A 的结果必须先经过人工 Review。

## 3. Stage 2A：当前复现基线

### 3.1 要回答的唯一问题

在当前软件/硬件环境下，使用历史隔离 worker 推理路径，已知的“推理心跳停止”是否仍可在一个短时、重复初始化的诊断窗口中复现？

### 3.2 历史基线

- 历史脚本：`projects/so101_L1/openvino/phase3_v2_9/run_isolated_gpu_stability_v2_9.py`
- 当前 SHA-256：`4fae4ce71896db4eafe01932b89076c46d11f401f6f64ad2fa3b78ae650cbab7`
- Phase 3 artifact manifest 中记录的 SHA-256：相同。
- 历史 Round 1：94.117618 秒后失去心跳，watchdog 恢复。
- 历史 Round 2：52.000131 秒后失去心跳，watchdog 恢复。
- 两次运行均为 GPU.0、FP32、LATENCY、warmup 10、stall 15 秒、startup 60 秒、telemetry 5 秒、window 60 秒。

### 3.3 保持不变的因素

- 不修改历史 Phase 3 脚本。
- 不修改 inference worker 函数。
- 不修改模型、参考输入、参考输出和容差。
- 不修改 OpenVINO、GPU plugin、内核、驱动、固件或电源设置。
- 使用 `GPU.0` Intel Arc iGPU、FP32、LATENCY。
- 使用 Queue 心跳和原父进程遥测路径。
- warmup 10、stall 15 秒、startup 60 秒、telemetry 5 秒、window 60 秒。

### 3.4 有意不同的因素

- 每次诊断窗口为 5 分钟，而不是资格测试的 30 分钟。
- 使用新的探索性 run ID 和 EXP-2026-003 证据目录，不写入或覆盖 Phase 3 已关闭证据。
- 运行前额外采集只读环境快照。

五分钟窗口不是稳定性验收。选择它是因为两次历史故障都在 95 秒内发生，而 Stage 2A 的问题只是“能否恢复故障信号”。

### 3.5 重复和停止规则

- 最多三次，每次重新创建进程和 OpenVINO 对象。
- 每次必须由人单独启动；禁止自动连续循环。
- 任意一次出现 watchdog timeout：立即停止 Stage 2A，不运行剩余次数。
- 每次完成后先检查证据完整性，再决定是否进入下一次。
- 三次均完成五分钟：停止，不追加第四次。
- 不因任何一次完成而恢复 GPU.0 部署资格。

最大主动 GPU 测量时间为 15 分钟，不含初始化和人工 Review。

### 3.6 运行前环境证据

每次运行前记录：

- UTC 和本地时间；
- 开机时长；
- 内核版本；
- OpenVINO 版本与设备列表；
- GPU.0 完整名称；
- 历史脚本及模型/参考文件哈希；
- 内存可用量；
- 与 GPU、训练、推理、benchmark 相关的进程列表；
- `/dev/dri` 使用者的 best-effort `fuser`/`lsof` 结果；
- 电源状态等无法可靠读取的项目必须标为 `UNAVAILABLE`，不能猜测。

环境快照只用于记录上下文，不把“未发现其他进程”解释成“绝对没有 GPU 使用者”。

### 3.7 每次运行的输出分类

只能使用以下状态：

- `HANG_REPRODUCED_WATCHDOG_RECOVERED`
- `NO_HANG_REPRODUCED_5M_COMPLETE`
- `CORRECTNESS_OR_NONFINITE_FAILURE`
- `STARTUP_OR_ENVIRONMENT_FAILURE`
- `UNEXPECTED_OR_INCOMPLETE`

不得把 `NO_HANG_REPRODUCED_5M_COMPLETE` 简写成 `PASS`。

## 4. Stage 2A 可能支持的结论

### 如果复现

可以说：当前环境中的历史 worker 路径仍能产生相同类别的“心跳停止”故障信号。

仍不能说：`request.infer` 内部哪一层是根因。因为历史心跳只在推理返回后发送，最后一个 heartbeat 与 watchdog timeout 之间还缺少调用边界证据。

### 如果三次都未复现

可以说：三个独立的五分钟诊断窗口内没有观察到历史故障。

仍不能说：故障已修复、旧证据无效或 GPU.0 已稳定。此时继续短时主动重跑的边际价值降低，应转为在未来真实事件发生时保存现场。

## 5. Stage 2B：仅在 2A 复现后设计

Stage 2B 目前只冻结原则，不冻结实现：

- 以 Stage 2A 的可复现路径作为 A 组；
- B 组每次只增加一种观察机制；
- 优先低频、低扰动的共享状态或外部观测，避免每次推理发送多条 IPC 消息；
- A/B 采用相同运行窗口、初始化方式、模型和环境记录；
- 预先冻结顺序、次数和停止条件；
- 如果观察机制使故障不再出现，只能形成“观察与复现率相关”的假设，不能称为修复。

可选观察层包括 Python 调用边界、进程/线程等待状态、系统调用边界或内核 GPU 报告。一次 Stage 2B 只选择其中一种。

## 6. 实施前必须解决的问题

- 如何在完全不修改历史 Phase 3 脚本和 worker 的情况下，把新证据写入 EXP-2026-003 目录。
- 如何让环境快照失败时仍保留明确的 `UNAVAILABLE` 记录。
- 如何验证 wrapper 只改变证据目录，不改变 worker 目标和运行参数。
- 如何避免把新的探索运行误计为 Phase 3 Round 3。

这些问题解决并经过静态 Review 前，不执行 Stage 2A。

### 当前实现状态

- `capture_stage2a_preflight.py`：只读采集环境上下文，不初始化 OpenVINO/GPU。
- `run_stage2a_historical_baseline.py`：校验历史脚本哈希、预检时效和轮次停止规则，再调用未修改的历史 worker；新证据重定向至 EXP-2026-003。
- 包装器只接受一个 `run-id`，其余 Stage 2A 参数在代码中冻结，避免命令行意外漂移。
- 协议已由 human owner 于 2026-09-24 接受并冻结。
- 冻结边界：最多三次、每次五分钟、逐次人工启动与复核；任意一次复现立即停止；三次未复现也停止；所有结果均不恢复 GPU.0 准入。

## 7. 人工 Review 问题

1. 为什么 Stage 2A 先追求“恢复故障信号”，而不是马上寻找根因？
2. 为什么三次五分钟未复现仍不能证明 GPU.0 稳定？
3. 为什么任意一次复现后就应停止 2A，而不是把三次全部跑完？
4. 为什么 Stage 2B 必须一次只增加一种观察机制？

## 8. Stage 2A 执行记录

### Round 1 — `stage2a_r1_20260924_01`

- 分类：`NO_HANG_REPRODUCED_5M_COMPLETE`
- 测量时间：300.006211 秒。
- 推理次数：15,750；序号连续。
- 非有限输出：0。
- correctness failure：0。
- 最大绝对误差：`1.430511474609375e-06`。
- worker exit code：0。
- watchdog timeout：false。
- 决策：不进入 Stage 2B；按冻结协议允许为 Round 2 采集新的预检证据。
- 边界：此结果不是 PASS，不改变 GPU.0 准入状态。

### Round 2 — `stage2a_r2_20260924_01`

- 分类：`NO_HANG_REPRODUCED_5M_COMPLETE`
- 测量时间：300.001901 秒。
- 推理次数：15,734；序号连续。
- 非有限输出：0。
- correctness failure：0。
- 最大绝对误差：`1.430511474609375e-06`。
- worker exit code：0。
- watchdog timeout：false。
- 决策：不进入 Stage 2B；按冻结协议允许为最终 Round 3 采集新的预检证据。
- 边界：Round 1 与 Round 2 合计十分钟未复现不是稳定性 PASS，不改变 GPU.0 准入状态。

### Round 3 — `stage2a_r3_20260924_01`

- 分类：`HANG_REPRODUCED_WATCHDOG_RECOVERED`。
- 最后完成推理：4,450。
- 最后完成时间：84.680417 秒。
- 最后完成输出：finite、correct，最大绝对误差 `1.430511474609375e-06`。
- watchdog：15.074460 秒无心跳后触发。
- timeout 时 worker：running、CPU 99.9%、RSS 623,583,232 bytes、37 threads。
- recovery：SIGTERM；worker exit code `-15`。
- 事后内核日志：故障时间窗无条目；不能据此排除内核/驱动问题。
- 决策：Stage 2A 立即关闭，禁止 Round 4；允许设计但不执行 Stage 2B。
- 边界：该结果复现症状类别，不定位 `request.infer` 内部根因，不改变 GPU.0 不准入状态。
