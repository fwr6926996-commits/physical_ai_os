# EXP-2026-003 Stage 2E-A Preflight Review

日期：2026-10-01  
run id：`stage2e_a1_20261001_01`  
正式 preflight：`evidence/stage2e_preflight/stage2e_a1_20261001_01.json`

## 1. Verdict

`PASS_FOR_ONE_TIME_BOUNDED_HANDOFF`

正式 preflight SHA-256：
`1f74c02590342cfdb95cde11c30f3b7b54d3b015c041050c5531be002c4f1367`

## 2. 已确认

- 在本机权限环境采集，PID `467657`，不是 sandbox PID namespace；
- `/dev/dri` 使用情况成功读取，状态为 `CAPTURED`；
- `ptrace_scope=1`，仍使用 worker scoped `PR_SET_PTRACER`，没有修改系统全局策略；
- AC online，platform profile 为 `performance`；
- OpenCL Runtime Build ID 为 `58ccca242c62c0629c06940ee3d7b8a40b298e35`；
- baseline、worker、runner、offset helper、preflight、GDB 和 `libigdrcl.so` 共七项 hash
  与 frozen manifest 一致；
- 尚无 `evidence/stage2e/stage2e_a1_*`，一次性 attempt 尚未消耗。

## 3. 被保留但不可用于执行的记录

第一次 preflight 在 Codex sandbox 内产生：

`evidence/stage2e_preflight/stage2e_a1_20261001_01_sandbox_invalid.json`

它显示 PID `2` 且 `/dev/dri` 不可见，已明确保留为 `sandbox_invalid`，不会被 runner 读取。

## 4. 时效与停止规则

正式 preflight 时间为 `2026-10-01T01:42:02+08:00`。runner 强制要求 preflight 年龄不超过
30 分钟，因此本次 handoff 必须在本地时间约 `02:12` 前启动。过期时不得绕过检查，必须生成
新 run id 和新 preflight。

本次只允许一个真实 attempt；无论复现或未复现都不得自动重试。

