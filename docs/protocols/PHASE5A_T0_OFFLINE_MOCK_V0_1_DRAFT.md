# Phase 5A T0 离线时间契约与 mock 停止协议草案

Protocol ID: `P5A-T0-L-0.1`

Status: `DRAFT_NOT_FROZEN_NOT_AUTHORIZED_TO_IMPLEMENT_OR_RUN`

Owner: human；设计与证据整理：Codex

Date drafted: `2026-10-27`（Asia/Shanghai）；Date frozen: `NOT_RECORDED`

Classification: 拟为 `QUALIFICATION`，只覆盖固定合成向量下的软件时间判断和 mock 输出证据；当前未执行。

Governing requirements: L1 V2.9 §3/7、Addendum 01 Gate T0、Addendum 02、`SIG-A0-ACCEPT-20261027-01`。

## 问题与结论范围

第一步回答：输入时间和动作身份不满足契约时，软件是否拒绝比较/输出；动作到期且没有替代有效动作时，能否以完整观察窗口证明 mock 输出为零？
通过时只可判 `T0_L_LOGIC_AND_MOCK_EVIDENCE_PASS`，不直接判整个 Gate T0、ROS 功能闭环、ActionBuffer 并发或物理停止通过。
本草案不修改五类核心契约；测试中的 `mock_token` 只代表一个待判定的动作标识，不规定 ACT 动作块长度、单位、轨迹点采样或夹爪映射。

SIG-A0 已接受的是上游处置和职责边界。本协议的字段、示例阈值与执行范围仍需审查和冻结；它不是运行授权。

## 设计文件与输入身份

设计输入在 `experiments/EXP-2026-004_sig_a0_alignment/acceptance_20261027/`：

- `timepoint_v0_1_draft.schema.json`：TimePoint 的 JSON 结构表达草案，不是已生成的 ROS `.msg`。
- `t0_test_vectors_v0_1_draft.json`：固定时间点和 16 个用例；所有数字均为合成例子。
- `design_artifact_manifest.json`：本次文件 SHA-256；未来冻结须同时固定实现/runner 身份，不能只固定数据。

基准代码 revision 为 `WORKTREE_BASE:3f141d0c444fbacea62d3d5b788980d437c95aad`；没有新的 Runtime 实现。
模型、相机、LeRobot、OpenVINO、MCU、串口及 ROS graph 在 T0-L 中均不使用，不激活已准入的 Phase 4 后端。

## 时间与身份契约草案

| 项目 | 本版建议 |
|---|---|
| 必要元数据 | timestamp、unit、clock_domain、source、measurement_point、synchronization_status、contract_version；加 session_id 与 validity |
| timestamp | JSON 使用有符号十进制整数字符串，单位 ns，精确解析到 int64；避免 JSON 数字经浮点链路损失纳秒精度 |
| 无效读数 | validity=INVALID 且 timestamp=null；0 是合法的合成 steady 起点，不代替未知 |
| domain | HOST_STEADY / SYSTEM_TIME / ROS_TIME / CAMERA_DEVICE / MCU_UPTIME；同类别不自动同源 |
| source | 在运行 manifest 中定义的时钟实例身份，包括主机/启动代际/时钟机制；进程 PID 不是时钟实例身份 |
| session_id | producer 与 executor 共用本轮 runtime session；任一端重启或 replay 时间代际变化时，旧许可/session 失效并清理旧动作 |
| measurement_point | 说明 capture/generated/dequeue/execute 等事件；valid_until 是 derived_expiry，须能追溯生成时刻与 lifetime |
| synchronization_status | SAME_SOURCE / UNSYNCHRONIZED / UNKNOWN / MAPPED_VALID；T0-L 不实现跨域映射，MAPPED_VALID 也不能绕过来源验证 |
| contract_version | `phase5a.t0.timepoint/0.1-draft`；不兼容版本直接拒绝 |

JSON Schema 只检查结构。时间范围、来源身份、同源关系、测量点先后与有效期必须由后续语义检查验证；结构合法不等于时间有效。
HOST_STEADY 首步只允许同一已登记来源和 session 内的比较；未同步、来源不同或版本不兼容时不计算 age。
未来真正的 host monotonic 来源要记录具体 API、主机与 boot 身份。不能仅因 Python 与 C++ 都叫 monotonic/steady，就假定实现可以混算。

## 判定顺序草案

1. 验证数据结构、版本、int64 范围和 validity；非法时拒绝，不输出命令。
2. 验证当前 session；本版遇到 MAPPED_VALID 先返回 MAPPING_NOT_SUPPORTED，再按 clock_domain、source 和同步状态的顺序检查其余记录。未知/不同源/未验证映射拒绝，age 标 unavailable；原因优先级以向量文件为准。
3. 检查观测→生成→消费的先后关系和有效区间；未来时间、倒置有效期按明确原因拒绝。
4. 使用半开区间：`now < valid_until` 才可能有效，`now >= valid_until` 即到期；相同动作只递增一次 expired-drop。
5. 源 Observation Age 单独判断；动作生成较新不能抵消观测过旧。向量中的 100 ms 仅为合成边界，不是实际控制需求。
6. 接近 mock sink 输出时复查；若中间延迟使动作过期，拒绝输出。需要单独记录检查与输出尝试事件，不能把两者合并成同一时刻。
7. 无有效动作则停止模拟命令。软件自身的输入失效/不输出原因与五类 SafetyState 的转换要在后续 ROS 协议中明确，本版不新增 SafetyState 枚举。

## 对照与用例

每个用例独立重置初始状态。正常同源、同 session、有效动作是对照；每个负向用例只改变表中列出的故障因素。
具体输入和预期值以固定向量文件为准，不允许运行后改预期。

| ID | 唯一改变项或受控场景 | 预期判断 |
|---|---|---|
| T0-01 | 有效动作，消费 80 ms、截止 100 ms | ALLOW；Action Age=80 ms |
| T0-02 | 消费恰好为截止 100 ms | REJECT / EXPIRED |
| T0-03 | 消费 120 ms，截止 100 ms | REJECT / EXPIRED |
| T0-04 | now 来自 MCU_UPTIME | REJECT / CLOCK_DOMAIN_MISMATCH；不产生伪 age |
| T0-05 | 相同 domain，不同主机/boot 来源 | REJECT / CLOCK_SOURCE_MISMATCH |
| T0-06 | 旧 session 的动作进入新 session | REJECT / SESSION_MISMATCH |
| T0-07 | 无效/缺失时间读数 | REJECT / INVALID_TIMESTAMP |
| T0-08 | 声称 MAPPED_VALID，但本版没有已验证映射 | REJECT / MAPPING_NOT_SUPPORTED |
| T0-09 | fake wall time 回拨，steady 判定输入不变 | 结果与 steady 对照一致；不改操作系统时间 |
| T0-10 | 动作较新，源观测已有 200 ms，合成 age 限制 100 ms | REJECT / OBSERVATION_STALE |
| T0-11 | 无新动作；连续观察停止窗口 | 11 个消费 tick，零命令，expired-drop 仅为 1 |
| T0-12 | 同一停止窗口缺少结束/完整计数证据 | EVIDENCE_INCOMPLETE，不能判停止 PASS |
| T0-13 | timestamp 超 int64 上界 | REJECT / TIMESTAMP_OUT_OF_RANGE |
| T0-14 | timestamp 为 NaN 字符串 | REJECT / SCHEMA_INVALID |
| T0-15 | 80 ms 检查后延迟至 120 ms 才尝试输出 | sink 前复查 EXPIRED，零命令 |
| T0-16 | 合成 ROS/replay 时间回拨并切换 session | 旧动作 SESSION_MISMATCH，不因重发布重新有效 |

T0-11 的窗口为 `[120 ms, 340 ms)`，虚拟 tick 间隔 20 ms，tick 在 120…320 ms，共 11 次。
340 ms 记录 WINDOW_END 和最终 sink 计数；窗口无新有效动作输入。只在首次移除过期动作时递增计数，后续空队列 tick 不重复递增。
这些数字不构成 50 Hz 控制能力、停止时延或真实调度保证。

## 运行上限与停止规则草案

- 正式实现及运行需单独授权，并冻结实现/runner、schema、输入、阈值、输出路径和源 identity；当前没有可执行入口命令。
- 拟定每个固定快照最多 1 次正式 suite，16 个用例各一次；无 warmup、无随机负载。失败后停止，不自动重跑；先形成诊断/修订。
- T0-L 的 virtual time 由向量驱动，不 sleep；建议 wall watchdog 为 10 s，只限制逻辑 suite，超时立即停止。
- 建议每个 suite 事件总量上限 256 条，单条不超过 16 KiB，总输出不超过 1 MiB；超过或关键事件丢失即证据失败，不无界积压。
- 未授权访问网络、ROS graph、设备文件、模型环境，或发生写出约定目录、异常、卡住、计数不一致时停止。
- 输出使用独立 `artifacts/phase5a/t0/<run_id>/`，仅保留证据并释放本轮本地资源；不清理既有证据、不修改系统配置。

## 指标与 PASS/FAIL

硬 PASS：16 个用例均匹配预期决策/原因；允许样例的 age 精确匹配；拒绝样例没有 mock 命令；停止窗口证据完整；计数与事件一致；所有输入与实现 identity 可追溯。
任何不匹配为逻辑 FAIL；记录缺失、watchdog、输出超限或版本/hash 漂移为 EVIDENCE_INCOMPLETE / INVALID_RUN，不能转为 PASS。
测试执行耗时、主机负载仅记录诊断，不验收实际控制频率、P99 或物理停止时延。

## 证据约定

- run_manifest.json：协议版本、run/session、源/实现/fixture hashes、环境身份和授权引用。
- events.jsonl：case、event 序号、measurement_point、TimePoint、动作标识、decision/reason、tick index 和计数。
- mock_commands.jsonl：实际 mock sink 输出的独立序号与关联动作；不能只记录“准备输出”。
- evidence_summary.json：窗口起止、期望/实际 tick、命令数、拒绝/expired 数及 recorder loss；缺失终点或未知丢失不能证明零输出。
- result.json：各 case 的 expected/actual 与 bounded verdict；不可只写 done。
- hashes.json 与 REVIEW.md：文件身份、独立核对、偏差及结论边界。

## 进入后续 ROS mock Stage 的条件

先取得本协议的实现/运行授权并完成逻辑验证，然后另定 ROS 实际配置与协议：RMW/DDS、QoS、Executor/Callback Group、Lifecycle、进程退出与许可失效、动作块、有限缓存、日志背压、rosbag 回放与 use_sim_time 负向测试。
ROS 时间验证只通过受控 `/clock` 或可审计的注入层进行，不能修改系统 wall clock。完整 Gate T0 所需的实际配置/负向测试证据仍须补齐。
ActionBuffer 并发/背压和 RT0/性能追踪按原阶段要求推进；不因本逻辑 suite 而宣称 Gate R/C/PR 或实时/物理安全通过。

## 冻结前核对

- [ ] 用户已理解本协议的时钟比较与证据边界。
- [ ] schema、测量点、session 及拒绝顺序已审查；实现与输入 hashes 已固定。
- [ ] 确认示例阈值只用于合成验证，没有替代实际任务预算。
- [ ] 运行入口、隔离范围、stop/recovery、输出上限及授权已记录。
- [ ] JSON Schema 的标准校验与语义检查分别验证；未将结构检查充当 T0 通过。

## 参考

- ROS 2 [Clock and Time](https://design.ros2.org/articles/clock_and_time.html)：区分时钟抽象，ROS time 可暂停或回拨。
- JSON Schema [2020-12 Validation](https://json-schema.org/draft/2020-12/json-schema-validation)：本草案使用对象、required、类型与字符串约束；跨记录语义不由这些关键词自动保证。
- 源执行书及 Addenda 摘录：`experiments/EXP-2026-004_sig_a0_alignment/governing_extracts.txt`。

## 偏差

无执行，尚无运行偏差。未来冻结与运行后不得覆盖预期或删除失败记录。
