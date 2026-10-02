# EXP-2026-003 Stage 2A Round 2 Review

## Verdict

`NO_HANG_REPRODUCED_5M_COMPLETE`

Round 2 完成冻结的五分钟历史 worker 路径，没有复现心跳停止。它不是稳定性 PASS，也不是 GPU.0 准入证据。

## Evidence integrity

- 运行 ID：`stage2a_r2_20260924_01`
- 设备：Intel Arc iGPU `GPU.0`
- OpenVINO：`2026.3.1-22476-759c5a6ab8c-releases/2026/3`
- 测量时间：300.001901 秒
- 推理行数：15,734
- 推理序号缺口：0
- 非有限输出：0
- correctness failure：0
- 最大绝对误差：`1.430511474609375e-06`
- worker exit code：0
- watchdog timeout：false
- recovery：null

证据 SHA-256：

- `result.json`: `f61660fe9465c184d56bcdc6c2ed75e96bf18b9b3caf63aa4a074c535f9697e1`
- `latencies.csv`: `83bab11280202754589955fe6570a728aa52d6aabdd30155479749bc258a7eab`
- `supervisor_telemetry.csv`: `242c7232c93ecb8b9ba284c0167d6c5665002c7fb5cd3bf786fa86892806e285`
- `stage2a_classification.json`: `b855f493b3b2457ff0ea586a122cbb6f9b309e9a673a2b2e8714cac50a601094`

## Comparison with Round 1

| Metric | Round 1 | Round 2 |
|---|---:|---:|
| Iterations | 15,750 | 15,734 |
| Mean latency ms | 18.990 | 19.007 |
| p50 latency ms | 18.300 | 18.314 |
| p95 latency ms | 25.157 | 25.159 |
| p99 latency ms | 29.757 | 29.620 |
| Maximum latency ms | 77.568 | 89.490 |
| Maximum sensor temperature °C | 72 | 72 |

两轮中心延迟和尾部百分位非常接近。最大单次延迟不同，但都正常返回，不能把单个最大值解释为失稳趋势。

Round 1 与 Round 2 合计完成 31,484 次测量推理和约十分钟测量，当前故障信号仍未恢复。

## Supported conclusion

在两次分别初始化的当前环境运行中，未修改的历史 worker 路径均完成五分钟，表现具有重复性，且没有观察到历史心跳停止。

## Unsupported conclusions

- 不能说 GPU.0 已稳定、故障已修复或旧失败无效。
- 不能把十分钟分段运行等同于一次连续30分钟资格测试。
- 不能进入 Stage 2B，因为仍没有可复现故障信号。
- 不能依据相近延迟排除驱动、runtime、plugin、调度或外部环境问题。

## Next decision

按冻结协议只允许最终 Round 3。Round 3 必须重新预检并单独 Review。无论 Round 3 是否复现，都禁止 Round 4。
