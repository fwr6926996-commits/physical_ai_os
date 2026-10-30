# Phase 5A T0 时间判断与停止证据协议候选

Protocol ID: `P5A-T0-L-0.2`

Status: `DESIGN_REVIEW_CANDIDATE_NOT_ACCEPTED_NOT_AUTHORIZED`

Date: `2026-10-27`（Asia/Shanghai）；owner: human；设计审查: Codex。

本版把 0.1 的时间契约与用例补到可供人审的程度。SIG-A0 接受范围不变；0.1 及既有接受/同步记录保持原样。
当前只进行了数据、Schema 和协议的静态核查，没有实现时间判断器、ActionBuffer 或 runner，也没有取得 T0 运行结果。

## 要决定的问题

是否接受首轮只处理**当前受信运行上下文中，同一 session、同一已登记 HOST_STEADY 时钟实例**的时间判断；对其他来源、跨域映射和证据不完整的情况，明确拒绝判断或输出？

这种取舍允许先验证一个有界的软件路径；它会保守拒绝尚未建立可比关系的时间，不尝试猜 offset 或用“数值看起来接近”放行动作。
不接入相机、模型、ROS graph、MCU 或设备文件，不调整系统时钟，不安装依赖。

## 一页原理

`clock_domain` 表示时钟类别，`source` 表示具体实例。两个主机都使用 HOST_STEADY，不代表计时起点一致。
同一主机的两个进程，只有在确认使用同一实际时钟实例且属于当前有效 session 后，才能把对应事件读数用于本版计算。
运行上下文必须由启动配置/manifest 提供，不能从收到的动作里反推“当前 session”或“当前时钟”。
本逻辑 suite 核对的是给定元数据与上下文的关系；真实采集代码是否正确绑定来源，需要后续集成证据，不能由标签自洽推定。

| 情形 | 本版处理 |
|---|---|
| 当前 session、已登记 host-A 来源，消费 80 ms、截止 100 ms | 可以继续检查有效性 |
| 同样的 80/100 数字，但消费时间来自 host-B | CLOCK_SOURCE_MISMATCH；不发布 Action Age 或“动作已过期”的结论 |
| 所有字段都自洽地来自 host-B，但当前控制来源是 host-A | 仍拒绝；报文内部一致不等于符合当前控制上下文 |
| 所有字段都来自同一个 SYSTEM_TIME | CLOCK_DOMAIN_NOT_PERMITTED；首轮控制有效期不使用可跳变的 wall clock |
| 声称来源为 host-A，但 domain 与登记信息冲突 | CLOCK_SOURCE_METADATA_MISMATCH |
| 时间同源，但动作属于旧 session | SESSION_MISMATCH；时钟可比不代表执行许可仍然有效 |

数字相减正确、动作仍有效、允许输出及停止证据完整，是不同判断。本版只验证下述合成用例规定的软件判断。

## 固定设计输入

候选文件目录：`experiments/EXP-2026-004_sig_a0_alignment/t0_design_review_20261027/`。

- `timepoint_v0_2_candidate.schema.json`：TimePoint 的结构候选。
- `t0_test_vectors_v0_2_candidate.json`：37 个命名时间点、34 个用例及受信运行上下文。
- `REVIEW.md`：与 0.1 的差异、实测到的 Schema 边界问题及审查范围。
- `design_snapshot.json`：本轮候选输入的 SHA-256；这不是已冻结的运行快照。

JSON 中时间读数保留为十进制整数字符串，单位 ns。结构层拒绝浮点数、NaN、非规范符号/前导零和末尾换行。
Schema 可接受的整数字符串仍可能超出 int64；语义层必须检查范围。HOST_STEADY 的负值无效；null/INVALID 不冒充零。
TimePoint 的 session 与来源身份不替代原 PolicyOutput 的 sequence_id；mock_token 是本版的测试标识，不重新定义 ACT 动作块。

## 受信上下文与检查顺序

固定向量中的 `runtime_context` 是测试 harness 的设置，不属于动作 payload。`runtime_context_overrides` 只用于明确的合成故障设置，不允许生产报文覆盖它。
来源登记表、当前 session、允许的控制 domain、当前控制 source、观测年龄边界和空映射表，均在运行前进入 manifest 并固定身份。

顺序以向量中的 `decision_precedence` 为准：

1. 结构/版本 → int64 范围 → INVALID/null 或负 steady 时间。
2. 与受信当前 session 一致 → 来源已登记 → 来源 metadata 与登记一致。
3. 本版不支持 MAPPED_VALID；不能因为报文自称有映射就进入跨域相减。
4. 各时间 domain 一致 → domain 允许用于控制判断 → 各来源与当前控制 source 一致 → 同步状态有效。
5. 核对输入角色的 measurement_point；capture、generated、derived_expiry、dequeue、execute_attempt 不混用。
6. 核对顺序：capture ≤ generated ≤ dequeue，generated < valid_until；sink attempt 不早于 dequeue。任何不满足返回 INVALID_TIME_ORDER。
7. 使用半开有效区间；`now >= valid_until` 返回 EXPIRED。再独立核对源 Observation Age。
8. sink 前重新检查上下文与有效期，避免消费检查后仍有排队延迟；拒绝时不得生成 mock 命令。

所有时间元数据错误都先于年龄计算处理，age 输出为 unavailable/null，不能把不成立的相减结果当诊断数字发布。
同源且顺序成立的 EXPIRED/OBSERVATION_STALE 情况可以保留相应 age 作为合成诊断。失效原因的优先级固定，不能实现时任意选择一个拒绝原因就算通过。
valid_until 在本版由向量显式给定；可报告 expiry-generated 的有效区间长度，不据此证明真实策略的生成过程或任务 lifetime 选择正确。

## 34 个用例的覆盖

T0-01…16 保留原问题类别。T0-04/05/06/08/16 的来源或 session 反例改为数值上仍有效的 80 ms，避免同时到期掩盖本来要检验的机制。
默认合成 Observation Age 上限为 1000 ms；仅 T0-10 使用 100 ms 上限，以独立暴露“新动作基于旧观察”的问题。

| 用例 | 核心预期 |
|---|---|
| T0-01 / 02 / 03 | 有效、恰好到期、到期后的边界 |
| T0-04 / 05 / 06 / 08 | domain、来源、session、未支持映射的拒绝；不能借过期掩盖 |
| T0-07 / 13 / 14 | 无效时间、int64 越界、NaN 结构错误 |
| T0-09 / 10 / 15 / 16 | fake wall 回拨、源观测陈旧、sink 前到期、replay 重置 |
| T0-11 / 12 | 完整停止观察窗与缺少终点/最终计数的反例 |
| T0-17 / 18 | 未登记来源与来源元数据伪装 |
| T0-19 / 20 | 全部采用 wall clock 或同步状态未知时拒绝 |
| T0-21 / 22 / 23 | capture 晚于 generated、generated 晚于消费、非正有效区间 |
| T0-24 / 25 / 26 / 30 / 33 | 负 steady、JSON 数字替代字符串、测量点错置、版本不兼容、末尾换行 |
| T0-27 / 29 | sink 时间倒退；全套字段内部一致但属于另一控制来源 |
| T0-28 / 32 / 34 | recorder loss、观察者没有进展、事件序号有缺口 |
| T0-31 | 停止窗口中确有一条 mock 命令，必须判停止行为失败 |

T0-31 预期得到 FAIL_MOCK_STOP_WINDOW_ONLY；T0-12/28/32/34 预期得到 EVIDENCE_INCOMPLETE。
suite 的通过条件是各实际结果与各自预期相符，而不是把所有 case 的结果字符串强制写成 PASS。
没有真正执行这些用例前，不将 expected 字段计为测试结果。
T0-09/16 仅检验给定虚拟读数、已声明 replay reset 后的处理，不证明真实 ROS 或系统时钟跳变的检测机制已经实现。

## 停止窗口证据

窗口为 `[120 ms, 340 ms)`，虚拟 tick 间隔 20 ms，要求 120…320 ms 共 11 次进展；340 ms 必须有 WINDOW_END。
期间没有新有效 token，实际 sink 记录为零、sink 首尾计数相同、expired-drop 只对移除的同一 `(session_id, mock_token)` 计一次。

停止判定必须交叉核对：

- 窗口起止、退出原因和预期/实际 tick 时刻；少 tick、重复 tick、窗口错位或异常提前退出均不能证明完整观察。
- 实际 mock sink 记录与首尾计数；计数一致但非零输出，仍不能判停止通过。
- recorder loss=0；关键事件序号连续，事件数量与记录相符；缺记录时不能相信一个自报 `evidence_complete=true` 标志。
- 过期动作的标识、检查时间、有效期、拒绝原因与过期计数关联。

候选向量中的 evidence 是构造的验证器输入，不能冒充运行日志。未来 runner 必须从实际输出证据独立重算结果，不能复制 expected 或输入中的完整性声明。
本版证明的“停止”始终仅指不再输出新的 mock 命令；不代表真实执行器、已有轨迹或机械系统停止。

## 实现范围与冻结分层

本候选当前不授权编码或运行。避免把“尚无实现 hash”误当成无法开始设计的循环，明确分两层：

1. **设计接受与有界实现授权**：人类审查本协议、Schema、向量、上下文及证据规则；可一次性明确是否允许下述本地实现、开发验证和条件满足后的一次正式 suite。
2. **运行快照冻结**：在已获实现授权的前提下完成代码和开发验证，保留开发结果；正式 suite 前固定协议/Schema/向量/实现/验证器/环境/命令的 SHA-256、run_id、授权引用和输出目录。缺任何条件都不启动正式 suite。

若没有条件式正式运行授权，开发验证结束后停止在冻结候选处。若人类已明确批准“开发检查通过并冻结后运行一次”，满足该条件后可继续，无需重复索取同一授权。
开发失败可以在已授权范围内修复实现并保留记录，不能通过修改预期来消除失败；修改设计输入需重新审查/版本化。

建议未来实现只包含：时间/身份判断、虚拟时钟适配、一次性 mock token 消费、JSONL mock sink、证据独立复核及入口 runner。优先使用已有 Python 与 jsonschema，不安装新依赖。
建议代码范围为 `runtime_core/phase5a_t0/`，有意义的回归检查放在 `tests/phase5a_t0/`；此处只是范围提议，目录尚未创建。
测试验证实现与证据复核，不要求用户手写 Schema、哈希或重复收集日志；用户关键操作是审查这个时钟取舍及之后一份实际证据。

## 运行边界候选

- T0-L 不导入 ROS、OpenVINO、LeRobot 或设备驱动；不启动节点、daemon、通信 socket、相机或硬件。
- 虚拟时间由向量驱动，不 sleep；拟用父进程 10 s wall watchdog，只用于阻止逻辑 suite 卡住，不作为实时性指标。
- 开发验证与正式资格输出分开标记并保留。正式 suite 每个冻结快照最多 1 次，34 个 case 各一次；失败、超时、证据不完整立即停止，无自动重跑。
- 正式 suite 事件上限 512 条，单条最多 16 KiB，总输出最多 1 MiB；超限、关键证据丢失、异常或访问约定外资源时停止并判证据无效。
- 运行输出仅在 `artifacts/phase5a/t0/<run_id>/`；临时开发检查在 `/tmp/phase5a-t0-<id>/`。不删除既有证据、不修改系统配置。
- 进程重置仅指本地测试进程和合成 session；不涉及 MCU reset、固件或真实执行许可。

## 所需输出与判定

正式输出包含 run_manifest.json、events.jsonl、mock_commands.jsonl、evidence_summary.json、result.json、hashes.json 和 REVIEW.md。
manifest 必须固定解释器和已有 jsonschema 的实际身份；正式证据复核独立于被测判断器，不能只相信它自报的计数。
硬 PASS 要求 34 个 case 均匹配固定预期、允许场景的 age 数值正确、被拒绝 token 没有 sink 输出、完整停止窗口成立，以及负向证据 case 能准确失败/判不完整。
未知来源或无可比时间时必须保留 unavailable，不填 0、NaN 或伪 age。

通过时只允许 `T0_L_LOGIC_AND_MOCK_EVIDENCE_PASS`；完整 Gate T0 仍需要实际配置下的时钟行为和负向测试证据。
ROS 2 阻塞/队列实验、实际 use_sim_time/rosbag2、ActionBuffer 并发、Gate R/C/PR、RT0、模型集成和物理安全均留在原后续 Gate。

## 当前审查结论

设计候选可供人审。Schema 和向量静态检查不等于时间判断实现或运行验证，也不接受整个 Gate T0。
SIG-A0 的既有接受不变，不重复要求批准架构。当前尚缺的是本版 T0 设计的决定，以及明确的本地实现/开发验证/正式 suite 范围。

参考：L1 V2.9 与 Addenda 摘录、已接受 SIG-A0 交接、[ROS 2 Clock and Time](https://design.ros2.org/articles/clock_and_time.html)、[JSON Schema 2020-12 Validation](https://json-schema.org/draft/2020-12/json-schema-validation)。
