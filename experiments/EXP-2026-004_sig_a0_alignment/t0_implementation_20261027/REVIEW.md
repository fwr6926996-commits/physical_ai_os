# T0-L 0.2 实现与一次正式 suite 审阅

Date: 2026-10-27（Asia/Shanghai）

Engineering result: `T0_L_LOGIC_AND_MOCK_EVIDENCE_PASS`

Human result acceptance: `PENDING`；完整 Gate T0：`NOT_ESTABLISHED`。

用户在解释 clock_domain/source/host/session 后回复“明白了，那我们继续”。本记录承接此前明确提出的 0.2 设计接受、本地实现/开发验证、开发通过且冻结后一次 34 用例 suite 的范围。原候选文件作为已审输入保留，不改写其历史状态；生效授权见 AUTHORIZATION.json。

## 已完成与证据

- 新增 runtime_core/phase5a_t0/：TimeJudge、一次性 mock token、消费检查及 sink 前重检、JSONL sink、独立证据读取和父进程 runner。
- 上下文由固定 harness 配置传入；动作不能选择当前 session/source。先检查身份/元数据，再算年龄；不可比情况 age=null。
- tests/phase5a_t0/test_t0.py：26 项回归检查通过，包含重复 token、过期计数去重、过期边界、观测陈旧、证据序号缺口、计数冲突及父进程 watchdog 分支。
- 三轮开发均 34/34；原始输出与单测日志保存在 development/。单测日志的 FAIL_STOPPED 来自有意 mock 的 watchdog 检查，不是开发 suite 失败。
- 正式运行前冻结协议/Schema/向量/代码/验证器/测试/授权、Python 3.13.12 解释器及已有 jsonschema 4.26.0 等模块身份、可信上下文、命令、run_id 和输出路径。依赖目录哈希用于记录身份，并非完整操作系统或环境镜像。
- 冻结记录 run_freeze.json；一次性领取记录 run_freeze.json.attempt.json。正式授权已用一次，未重跑。
- 正式输出：artifacts/phase5a/t0/T0-L-20261027-01/。result.json 记录 34/34 符合固定预期。
- audit_raw.py 只读重算事件/命令/年龄/序号/计数及哈希；raw_audit.json 记录通过。这是证据复核，不是再次执行 suite。

## 三个重点证据

| 对象 | 实际记录与含义 |
|---|---|
| T0-15 sink 前到期 | dequeue=80 ms 初检 ALLOW；execute_attempt=120 ms、valid_until=100 ms，重检 EXPIRED；mock_commands=0，expired_drop=1。消费放行不替代输出前重检。 |
| T0-11 实际停止窗口 | [120,340) ms 中 120…320 ms 共 11 次 tick；ACTION_REJECTED 包含 session-A/action-1、checked_at=120 ms、valid_until=100 ms、EXPIRED；过期计数=1；实际 sink 记录=0，首尾计数均0；WINDOW_END/NORMAL_END、loss=0、连续事件序号和最终记录数齐全。 |
| T0-31 故障证据输入 | SYNTHETIC_VERIFIER_INPUT 含一条140 ms命令，被判 FAIL_MOCK_STOP_WINDOW_ONLY/UNEXPECTED_MOCK_OUTPUT；这条构造命令不在实际 mock_commands.jsonl 中。 |

共采集 190 条实际 mock 事件、2 条实际命令（仅 T0-01/T0-09 允许场景）。6 个实际 mock 停止窗口各 11 ticks / 0 commands / expired_drop=1。83 条构造验证器事件单独保存在 verifier_inputs.jsonl，不冒充采集数据。合计273条事件，147289 bytes 输出；未触发512条/16KiB单条/1MiB总量/10s watchdog边界。wall耗时只用于watchdog，不形成实时性能结论。

用例 T0-12/28/32/34 的构造证据得到 EVIDENCE_INCOMPLETE；没有把缺证据当作零输出。suite 的 PASS 表示包括这些负例在内均符合预期。

## 支持的结论与下一步

已验证给定虚拟读数、可信配置和合成事件下的时间/身份判断、mock token 拒绝和有限停止窗证据复核。未验证实际时钟来源绑定、真实跳变检测、ROS通信/队列/跨进程集成、并发 ActionBuffer、模型、相机或硬件；未建立完整 Gate T0、Gate R/C/PR、RT0 或物理停止结论。

当前允许只读审阅这些证据、解释机制和设计下一份有界集成协议。最终有界结果接受仍由 Human Owner 决定；新运行或实际集成须另具明确范围与有效授权。本次正式 suite 不自动重跑。

学习关键操作：用户审阅上表和实际日志，确认“消费可放行但 sink 可到期”以及“停止依据是完整窗口和命令证据”。此前已有过期消费与停止证据理解记录，本轮不重复闭卷问答。
