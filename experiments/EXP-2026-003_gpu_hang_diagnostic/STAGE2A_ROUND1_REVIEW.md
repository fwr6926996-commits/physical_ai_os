# EXP-2026-003 Stage 2A Round 1 Review

## Verdict

`NO_HANG_REPRODUCED_5M_COMPLETE`

Round 1 完成了冻结的五分钟历史 worker 路径，没有复现心跳停止。它不是稳定性 PASS，也不是 GPU.0 准入证据。

## Evidence integrity

- 运行 ID：`stage2a_r1_20260924_01`
- 设备：Intel Arc iGPU `GPU.0`
- OpenVINO：`2026.3.1-22476-759c5a6ab8c-releases/2026/3`
- baseline source SHA-256：`4fae4ce71896db4eafe01932b89076c46d11f401f6f64ad2fa3b78ae650cbab7`
- 测量时间：300.006211 秒
- 推理行数：15,750
- 推理序号缺口：0
- 非有限输出：0
- correctness failure：0
- 最大绝对误差：`1.430511474609375e-06`
- worker exit code：0
- watchdog timeout：false
- recovery：null

证据 SHA-256：

- `result.json`: `de6179690a8db1e35f23876eb49554661f5533be62613e8f04a4f82a01c3cb27`
- `latencies.csv`: `5b042cd5600e96c0d552ee58b2d0ed6322c93d6d2454986f593a8d08c406a322`
- `supervisor_telemetry.csv`: `b4859b71861d56991d14bf29d9965fcda933e1784fcd5e8f15c8df3be1504e29`
- `stage2a_classification.json`: `9c049298eb28481089e61e0daa7c03ead24ec8701475474d40099ce3ecfa1752`

## Latency observation

| Evidence | Outcome | p50 ms | p95 ms | Mean ms |
|---|---:|---:|---:|---:|
| Historical Round 1 | hang at 94.118 s | 31.656 | 47.088 | 28.698 |
| Historical Round 2 | hang at 52.000 s | 31.652 | 47.247 | 28.902 |
| Stage 1 | no hang, 180 s | 18.193 | 27.644 | 19.457 |
| Stage 2A Round 1 | no hang, 300 s | 18.300 | 25.157 | 18.990 |

Stage 1 与当前历史路径 Round 1 的延迟接近，但都明显低于两次历史失败。这个相关性说明当前实际运行条件可能与 2026-09-16 不同，值得记录；它不能证明延迟变化导致或避免了挂起。

历史证据没有保存等价的电源 profile、DRM 使用者和系统工作负载快照，因此现在不能区分 GPU 频率、电源状态、桌面负载、调度状态或其他隐藏条件。

## Window review

五个完整的一分钟窗口平均延迟处于 18.939–19.106 ms，未观察到逐窗口恶化。最后一次推理在 300.006 秒返回，因此按历史脚本的窗口算法被计入 `window_index=5`；这一个残余样本是边界计算的正常结果。

## Supported conclusion

当前记录的环境下，未修改的历史 inference worker 路径完成了一个五分钟窗口，历史故障信号未出现。

## Unsupported conclusions

- 不能说 GPU.0 已稳定或已修复。
- 不能推翻 2026-09-16 的两次失败。
- 不能把更低延迟认定为不挂起的原因。
- 不能进入 Stage 2B，因为当前尚未恢复可观察的故障信号。

## Next decision

按冻结协议允许 Round 2，但必须先采集新的同名预检证据，并在 Round 2 后再次 Review。不得自动执行 Round 3。
