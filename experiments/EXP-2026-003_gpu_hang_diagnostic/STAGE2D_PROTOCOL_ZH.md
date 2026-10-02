# EXP-2026-003 GPU 挂起诊断 — Stage 2D 协议草案

协议编号：`EXP-2026-003-STAGE2D-BOUNDED-NATIVE-STACK-V1`

状态：`CLOSED_AFTER_ROUND1__ROUNDS2_AND3_PROHIBITED`

分类：`EXPLORATORY_DIAGNOSTIC`

本协议不属于 GPU.0 资格测试，不改变 `GPU.0 CLOSED_NOT_ADMITTED`，也不启动 Phase 4。

## 1. Stage 2C 已知事实

Stage 2C Round 1 再次得到：

```text
H = 653
R = 653
E = 654
```

第 654 次同步 `request.infer(inputs)` 进入但未在 watchdog 窗口内返回。

一次 timeout 后 `/proc` 快照观察到：

```text
主线程：R (running), wchan=0
其余 36 线程：S (sleeping), wchan=futex_do_wait
```

进程在 watchdog 观察区间约占用 94.9% CPU，但 syscall 和 stack 因权限不可读。

## 2. Stage 2D 要回答的唯一问题

当相同 infer-not-returned 症状再次出现时，GDB 在一个有界、timeout 后的单次快照中，把主线程观察在哪个用户态/原生调用栈和动态库边界？

Stage 2D 不尝试直接证明该函数、动态库或组件是根因。

## 3. 控制路径

继续沿用：

- 历史 Phase 3 isolated-worker supervisor；
- Stage 2B 的 infer enter/return 共享计数器；
- GPU.0、FP32、LATENCY、模型、输入、warmup、correctness、heartbeat、telemetry 和 watchdog 参数；
- 五分钟单轮上限；
- 原 SIGTERM/SIGKILL 恢复函数。

不继续执行 Stage 2C `/proc` 快照，避免把两个观察机制混入同一轮。

## 4. 唯一新增观察机制

Stage 2D 包含同一机制所需的两部分：

1. worker 启动时调用一次 `PR_SET_PTRACER(supervisor_pid)`，只允许 supervisor 及其后代在该 worker 生命周期内附加；
2. watchdog 已确认 timeout 后、原恢复动作之前，启动一次有硬时间上限的 GDB helper。

正常 infer 循环中不运行 GDB、不采样栈、不轮询线程。

`PR_SET_PTRACER` 是低频启动时变化，不是零扰动，也不是零安全影响。它必须作为 Stage 2D worker 相对 Stage 2B worker 的显式差异保存和审核。

## 5. GDB 快照草案

GDB 必须：

- 使用 `--batch --nx --quiet`；
- 禁用 pagination 和 confirm；
- 禁用 debuginfod，避免网络查询与非确定性等待；
- 附加目标 worker PID；
- 保存一次 `thread apply all bt 40`；
- 正常路径显式 detach；
- stdout/stderr 合并保存为原始证据；
- helper 总预算暂定 2 秒；
- 无论成功、部分成功、失败或超时，都继续原 SIGTERM/SIGKILL 恢复。

helper 超时必须终止 GDB。真实运行前，无 GPU integration mock 必须再次证明 tracer 被终止后 target 不会永久停在 traced/stopped 状态，且原恢复一定执行。

## 6. 为什么保留所有线程栈

问题聚焦主线程，但 GDB 的 thread 编号不应被假定等于 Linux PID/TID。保留一次所有线程栈可以：

- 通过 LWP/TID 找到主线程；
- 避免选错 GDB thread；
- 记录其他线程只是为了理解主线程调用关系，不把它们自动解释为死锁。

这仍然是一张同一时刻的栈快照，不是连续 profiler。

## 7. 结果分类草案

必须先保留 infer 边界分类，再增加 GDB 证据质量分类。

### Infer 边界

- `HANG_INFER_ENTERED_NOT_RETURNED`
- `HANG_AFTER_INFER_RETURN_BEFORE_HEARTBEAT`
- `HANG_AFTER_HEARTBEAT_BEFORE_NEXT_INFER`
- `BOUNDARY_EVIDENCE_INCONSISTENT`
- `NO_HANG_REPRODUCED_5M_COMPLETE`

### GDB 栈质量

- `GDB_STACK_COMPLETE_MAIN_THREAD_IDENTIFIED`
- `GDB_STACK_PARTIAL_MAIN_THREAD_IDENTIFIED`
- `GDB_STACK_UNUSABLE_MAIN_THREAD_NOT_IDENTIFIED`
- `GDB_ATTACH_FAILED`
- `GDB_AUTHORIZATION_INVALID`
- `GDB_HELPER_TIMEOUT`
- `GDB_NOT_TRIGGERED_NO_HANG`

## 8. 每类证据能支持什么

### 主线程顶部是带名字的函数

可以说：GDB 停住目标的瞬间，主线程调用栈顶部位于该函数。

不能说：该函数本身有 bug，或该函数所在组件一定是根因。

### 只能看到动态库和地址

可以说：快照把观察位置缩小到某个已加载模块和偏移附近。

不能根据一个地址猜测内部函数或控制流；若需要符号，另行评估匹配 Build ID 的调试符号。

### 栈顶部位于 Level Zero、OpenCL、GPU plugin 或 OpenVINO Runtime

可以记录观察到的跨库调用链，并据此选择下一条更窄的研究路径。

不能把“当前执行位置”直接写成“故障来源”。调用者、被调用者、等待对象、GPU 状态和此前事件仍可能是原因。

### GDB 无法展开

只能说本次观察机制证据不足。不能说被省略的层没有执行。

### GDB 暂停目标

必须记录 attach 到 detach/termination 的持续时间。GDB 会改变调度和恢复时刻，因此结果是诊断证据，不是自然运行时序的完整再现。

## 9. 重复与停止规则草案

- 最多三次，每次五分钟，每次由人单独启动并先做新预检。
- 第一次同时得到一致的 `HANG_INFER_ENTERED_NOT_RETURNED` 与可识别主线程的 complete/partial stack，立即停止并进入 Review。
- 如果 GDB authorization invalid、attach failed、helper timeout、目标保持 stopped、原恢复异常或 infer 边界不一致，立即停止并先修正机制。
- 三次均未复现：以 `INCONCLUSIVE_EVENT_DID_NOT_RECUR` 关闭。
- 禁止第四次。
- 任何结果均不恢复 GPU.0 准入。

## 10. 实现前检查

- 保存 Stage 2D worker 相对冻结 Stage 2B worker 的最小 diff；
- 在 worker ready evidence 中记录 `PR_SET_PTRACER` 返回码、errno 和授权 PID；
- 保存 GDB 版本、路径和 SHA-256；
- 保存真实 OpenVINO Runtime、Intel GPU plugin 和 Level Zero runtime 的 Build ID；
- 实现 helper timeout、raw output、attach/detach判定和恢复审计；
- 用普通 mock 验证成功、partial、attach failure、timeout、target-exited 和恢复路径；
- 冻结实现哈希；
- 在真实 GPU 执行前进行最终人工 Review。

## 11. Human Review 问题

1. 为什么调用栈能说明“快照时观察在哪里”，却不能直接说明“为什么挂起”？
2. 为什么真实库被 stripped 后，仍可能获得有用信息，但信息层级会下降？
3. `PR_SET_PTRACER(supervisor_pid)` 相比把系统 `ptrace_scope` 改成 0，安全边界有什么不同？
4. 为什么第一次取得可识别主线程的 hang stack 后就应该停止，而不是继续跑三次？

Human owner 已完成上述证据边界学习，并于 2026-09-30 允许进入实现和无 GPU mock。真实 GPU 执行仍需实现审计、冻结哈希和单独确认。
