# EXP-2026-003 Stage 2E-A Round 1 Review

日期：2026-10-01  
run id：`stage2e_a1_20261001_01`  
结论：`VALID_HANG_REPRODUCTION_AND_COMPLETE_MODULE_OFFSET_EVIDENCE`

## 1. 实验有效性

- frozen baseline、worker、runner、offset helper、preflight、GDB 和 OpenCL runtime hashes
  全部匹配；
- worker scoped `PR_SET_PTRACER` 成功，授权 PID 与 supervisor 一致；
- device 为 `GPU.0 — Intel Arc Graphics (iGPU)`；
- precision 为 FP32，performance hint 和输入/输出 artifact 均未改变；
- initial correctness 通过，最大绝对误差 `1.430511474609375e-06`；
- GDB helper return code 为 0，约 `0.921 s` 完成并正常 detach；
- detach 后 target 回到 `R (running)`，原 SIGTERM recovery 成功。

因此本轮不是诊断工具失败，也不是证据不完整。

## 2. infer 边界

最后完整完成的 measurement iteration 为 `6748`。计入 initial inference 和 10 次 warmup 后：

```text
H / return_sequence = 6759
E / enter_sequence  = 6760
E - R               = 1
```

两次共享计数器读取均为同一值，分类为：

`HANG_INFER_ENTERED_NOT_RETURNED`

worker 在约 132 秒后失去 heartbeat，15 秒 watchdog 触发时约占用 `99.9%` CPU，37 threads。

## 3. 稳定 module offset

主线程由 `LWP == worker PID == 467955` 明确识别。

```text
PC                  = 0x74aeb8e008c6
mapping_start       = 0x74aeb8a00000
mapping_end         = 0x74aeb914a000
mapping_file_offset = 0x0
mapping_permission  = r-xp
module              = /usr/lib/x86_64-linux-gnu/intel-opencl/libigdrcl.so
```

重新计算：

```text
PC - mapping_start + mapping_file_offset
= 0x4008c6
```

记录值与独立重算一致。Build ID 为
`58ccca242c62c0629c06940ee3d7b8a40b298e35`。

## 4. 两次故障的一致性

Stage 2D 与 Stage 2E 主线程顶部九个 `libigdrcl.so` frame 地址逐一比较后，每一帧的地址
差值都完全相同：`-0x69ca7800000`。换句话说，两次 ASLR load address 不同，但九帧内部相对
布局相同。

Stage 2E 得到的九个稳定 offset 为：

```text
#0  0x4008c6
#1  0x3cd8b9
#2  0x33082e
#3  0x4c5043
#4  0x1581ee
#5  0x1c4f6f
#6  0x13c6cd
#7  0x10b3dd
#8  0x0d2c2b
```

这强力支持 Stage 2D 和 Stage 2E 捕获的是同一条内部调用链，而不是两个随机停点。

## 5. PC 附近指令

PC `0x4008c6` 是：

```text
0x4008c2  tpause %ecx
0x4008c6  jmp    0x40073d
```

周围循环还包含：

- `pause` loop；
- 读取/调用 predicate；
- `system_clock::now()`；
- 时间差比较；
- `tpause`；
- `sched_yield()`；
- 条件满足后退出循环的路径。

这些机器码语义与精确版本源码
`shared/source/utilities/wait_util.h::waitFunctionWithPredicate()` 的 `pause/tpause → predicate →
yield` 结构高度一致。由于 binary stripped 且没有匹配 debug symbols，最严谨表述是：

> 主线程在 `libigdrcl.so` 内一个与 WaitUtils 用户态完成等待实现高度一致的循环中被观察到。

不能把它写成“已经由符号证明函数名”。

`addr2line` 显示的 `GTPin_Init at ??:?` 只是 stripped binary 中最近的导出符号范围，不能把
该位置归因给 GTPin。

## 6. 当前能够支持的结论

1. GPU.0 稳定性故障再次在有界实验中复现；这不是偶发的单次历史记录。
2. 同步 infer 已进入但没有返回。
3. 主线程没有停在 Python；它沿 OpenVINO → Intel GPU Plugin → Intel OpenCL Runtime 调用链
   进入 `libigdrcl.so`。
4. 两次 native snapshot 捕获到相同的九帧内部调用链。
5. 最新 PC 位于一个包含 `tpause` 和 `sched_yield` 的用户态等待/轮询循环。
6. 这能够解释“进程仍 running 且接近一个 CPU core”的表象。

## 7. 仍不能支持的结论

1. 不能证明 OpenCL runtime 是最初制造错误的组件；它可能在等待下游永远没有完成的工作。
2. 不能判断等待条件为何不满足，或 GPU task 是否提交、执行、完成但 completion tag 未更新。
3. 不能区分 GPU hardware、i915、OpenCL runtime、GPU plugin 或更早状态中的原始责任。
4. 不能从一个 stopped-time PC 判断循环中所有时间都停在同一条指令。
5. 不能据此决定升级/降级 runtime 一定有效。
6. 不能恢复 GPU.0 准入。

## 8. Evidence hashes

- baseline result: `eb256b650335dbdf8d427a9e3defa4d3d8bdaa9e9725b19052eff4eec677bc3a`
- Stage 2E result: `805902c2c651e7c3a1bbc60d074f049d934a80680fd5894143ad1caf18319b82`
- raw GDB: `49088c360b5d76a76700eff97806a8f3fad5d622a319b3eebe8d31264c91b68d`
- latencies: `0d9a7ca014cae892c75ce85b301555bbcdd9727e02333831f7b4d3cf8abb37b2`
- telemetry: `43a8ccbcb09693fa3c3c89177b5944c16e1bd526cc7a01005f1f5b499db66553`

## 9. Stop decision

Stage 2E-A 的唯一问题已经回答，单次批准已消耗。禁止自动重试或开展 Stage 2E-B。
