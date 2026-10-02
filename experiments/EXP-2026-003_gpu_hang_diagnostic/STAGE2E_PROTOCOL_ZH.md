# EXP-2026-003 GPU 挂起诊断 — Stage 2E-A 协议草案

协议编号：`EXP-2026-003-STAGE2E-A-MODULE-OFFSET-CAPTURE-V1-DRAFT`

状态：`CLOSED_AFTER_SINGLE_APPROVED_ATTEMPT__NO_RETRY`

分类：`EXPLORATORY_DIAGNOSTIC`

本协议不属于 GPU.0 资格测试，不改变 `GPU.0 CLOSED_NOT_ADMITTED`，也不启动 Phase 4。

## 1. 继承事实

Stage 2D Round 1 已得到一致的 `H=12396, R=12396, E=12397`，并在同一事件中取得完整
GDB all-thread stack。主线程从 `_pyopenvino`、OpenVINO Runtime、Intel GPU Plugin 进入
`libigdrcl.so`，但该库顶部帧只有 ASLR 绝对地址。

Stage 2D 已关闭，禁止用其 Round 2/3 名义继续执行。

## 2. 唯一问题

当相同 `HANG_INFER_ENTERED_NOT_RETURNED` 再次出现时，能否在一次有界、停止时快照中，
保存足够的主线程 PC/backtrace 和 module mapping 信息，把 `libigdrcl.so` 地址换算为稳定
module offset？

## 3. 唯一新增证据

在 Stage 2D 的单次 GDB attach 中，增加并保存：

```text
info sharedlibrary
info proc mappings
info threads
thread 1
bt 40
info registers pc
x/i $pc
```

实现不能只假定 GDB thread 1 是主线程；最终质量判定仍必须用 Linux LWP 等于 worker PID
来确认主线程。若命令选择依赖 thread 1，mock 和实现审查必须验证该假设，或者改为在输出中
提取主线程后再进行第二段命令。原始 GDB 输出必须完整保存。

## 4. 明确不做的事

- 不采集第二个时间点；
- 不连续 profiler；
- 不升级、降级或切换 driver/runtime；
- 不更改模型、输入、precision、device 或 performance hint；
- 不启用可能改变 runtime 路径的 debug flag；
- 不把 module offset 自动解释为函数名或根因；
- 不将本结果用于 GPU 准入。

## 5. 结果质量草案

- `OFFSET_EVIDENCE_COMPLETE_MAIN_THREAD_AND_MAPPING_IDENTIFIED`
- `OFFSET_EVIDENCE_PARTIAL_MAIN_THREAD_ONLY`
- `OFFSET_EVIDENCE_PARTIAL_MAPPING_ONLY`
- `OFFSET_EVIDENCE_UNUSABLE_MODULE_NOT_IDENTIFIED`
- `OFFSET_EVIDENCE_UNUSABLE_RAW_OUTPUT_NOT_SAVED`
- `GDB_ATTACH_FAILED`
- `GDB_HELPER_TIMEOUT`
- `GDB_AUTHORIZATION_INVALID`
- `GDB_NOT_TRIGGERED_NO_HANG`

“complete”至少要求：

1. infer 边界仍为 `HANG_INFER_ENTERED_NOT_RETURNED`；
2. worker PID 对应的主线程被识别；
3. 主线程栈/PC 位于 `libigdrcl.so`；
4. 同一次 attach 保存了包含该 PC 的 mapping 及其 file offset；
5. 原始输出写入成功；
6. GDB 有界退出或 detach，随后原 watchdog recovery 成功。

## 6. 证据换算规则

对包含 PC 的 executable mapping：

```text
stable_module_offset = pc - mapping_start + mapping_file_offset
```

必须同时记录原始 `pc`、`mapping_start/end`、`mapping_file_offset`、module path、Build ID 和
计算公式。若 mapping 输出缺少 file offset、PC 不在该 mapping 内，或 module path 无法唯一
对应 `libigdrcl.so`，不得猜测 offset。

## 7. 停止规则

- Stage 2E-A 最多允许一次真实 GPU attempt；不是预先承诺一定执行。
- 一次得到 complete offset evidence 后立即关闭。
- 任何 authorization、attach、mapping 解析、raw-output 保存、detach 或 recovery 异常，立即停止。
- 未复现则记录 `INCONCLUSIVE_EVENT_DID_NOT_RECUR` 并关闭本次 attempt；不得自动追加下一轮。
- 是否设计 Stage 2E-B 双快照，必须在 Stage 2E-A Review 后重新判断和批准。

## 8. 执行前 Gate

真实 GPU 运行前必须全部满足：

1. 无 GPU mock 证明 mappings、主线程、PC、raw output、detach 和 recovery 路径；
2. production wrapper 只相对 Stage 2D 增加本协议列出的取证命令和 offset 解析；
3. 独立审查主线程识别与 mapping 解析，防止把错误映射算成可信 offset；主线程必须按
   Linux LWP 等于 worker PID 选择，不能假定 GDB thread number；
4. 冻结脚本、worker、baseline、GDB 和 preflight 哈希；
5. 由 human owner 单独确认一次真实 Stage 2E-A attempt。

## 9. 当前决定

Human owner 于 2026-10-01 批准一次手动启动的真实 Stage 2E-A attempt。批准不包含自动重试、
第二次快照、环境变更或 GPU 重新准入。
