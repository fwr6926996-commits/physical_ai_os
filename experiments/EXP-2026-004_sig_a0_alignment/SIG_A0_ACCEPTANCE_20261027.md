# SIG A0 架构对齐接受与 Phase 5 设计交接

Decision ID: `SIG-A0-ACCEPT-20261027-01`

Decision date: `2026-10-27`（Asia/Shanghai）

Status: `ACCEPTED_ARCHITECTURE_ALIGNMENT_ONLY`

Decision owner: human

## 人类决定

用户在阅读对应文件后明确回复：

> 我已阅读对应文件并接受这个决定和对应架构

该回复接受上一轮 `review_20261027/HANDOFF_REVIEW.md` 的五项 SIG-A0 交接内容及对应架构。
上一轮提出的决定明确限定为上游处置、项目职责边界和进入 T0/首个 offline mock Stage 的协议设计，不包含编码、构建或运行授权。
本记录不要求再次批准同一个 SIG-A0 决定。

## 已接受的范围

1. 采用 `SIG-aware, SIG-independent`；Core 维持 Ubuntu 24.04 / ROS 2 Jazzy。
2. 上游源码只作为审查与参考，不引入新的运行依赖。组件处置按下表生效；不是上游兼容性或设备准入。
3. 五类项目契约、InferenceBackend、有限 ActionBuffer、RuntimeMetrics 与 SafetyFilter→MCU 许可/急停边界保持项目所有权；厂商与舵机私有表示留在 Backend/Adapter。
4. 首个架构方向为 ReplayObservation→FakePolicy→有限 ActionBuffer→周期消费→软件门控→日志 Mock Adapter。producer 与 executor 分进程，缓存唯一由 executor 拥有，监控不替代输出路径校验。
5. 下一步先具体化 T0 时钟契约及测试协议，再冻结首个本地 offline mock Stage。具体消息/API、动作块、容量/覆盖、QoS 和调度参数尚未冻结。

## 已接受的组件处置

| 组件 | 处置 | 重开条件 |
|---|---|---|
| ros2_so_arm | DEFER | 项目 mock 闭环完成，出现需要独立 ros2_control mock spike 回答的适配问题 |
| feetech_ros2_driver | DEFER | 真实硬件/安全协议、动作映射和许可链具备；兼容性先无硬件隔离评估 |
| Rosetta | DEFER | Observation/T0 契约明确，出现 bag→Observation 的具体对照问题，并固定关联依赖 |
| SIG demos | REFERENCE_ONLY | 若拟成为运行依赖，重新审查兼容性、边界及 ADR |
| ros2_policy_execution_pipeline | REFERENCE_ONLY | Phase 5B 比较执行放置与并发；若拟采用，先审查公共类型与失败语义 |
| native buffers / REP-0157 | DEFER | profiling 证明拷贝/序列化影响冻结指标，再立可行性协议 |
| REP-0158 / OpenUSD | DEFER | Technical Core 与 Employment Gate 后，E3 出现跨仿真资产需求 |
| Agentic / ROS MCP | DEFER | E5 正式开启且权限、安全及审计边界明确 |

完整依据仍见原组件矩阵；本表将其从建议更新为已接受处置，没有新增 ADOPT_AND_PIN 或 ADAPT_BEHIND_BOUNDARY。
Notion 的 19 条技术候选及原 L2 四项仅完成触发核对，没有因本次架构接受而自动改为“已采用”。

## 验收与未验收状态

| 项目 | 状态 |
|---|---|
| SIG-A0 有界架构对齐审查及 human handoff | ACCEPTED，限本记录范围 |
| 动作过期与 mock 停止证据的理解检查 | 已通过原记录的 OPERATOR 文本判断 |
| Phase 5A 职责边界与上游处置 | 已接受，细部契约仍需设计与冻结 |
| Gate T0 / Gate R / Gate C / Gate PR | 未经本记录取得 PASS |
| 上游构建、兼容性、退出/恢复测试 | 未执行、未准入 |
| Phase 4 CPU FP32 准入 | 保持原冻结输入、原目标身份与离线同步限定 |
| 编码、构建、ROS 节点/模型运行 | 本决定未授权 |
| 真机、串口、扭矩使能、MCU、固件、驱动或系统依赖变更 | 本决定未授权 |

## 接受依据与可追溯来源

- `review_20261027/HANDOFF_REVIEW.md`：用户阅读后接受的五项交接内容。
- `review_20261027/T0_DESIGN_DRAFT.md`：被接受的职责划分；时间字段和测试仍为草案。
- `component_dispositions.md`、`interface_mapping.md`：固定上游身份的处置依据与七项接口比较。
- `upstream_snapshot.json`、`review_20261027/OFFICIAL_SOURCE_REVIEW.md`：五个仓库、23 个文件及官方资料覆盖。
- `review_20261027/CANDIDATE_TRIGGER_REVIEW.md`：19+4 候选的双入口核对与触发边界。
- `review_20261027/LEARNING_CHECK.md`：原答、判断与后续验收条款。
- `acceptance_20261027/accepted_scope_snapshot.json`：本次接受所引用文件的 SHA-256 与源 revision。

10/26 与 10/27 的待接受审查、原始快照及验证文件作为历史保留，不回写成“当时已接受”。

## 下一步与重开条件

当前允许继续：本地资料与设计工作、T0 schema/测试向量/证据约定、首个 offline mock Stage 协议准备，以及按同步契约投影本决定。
后续进入实现/构建/运行时，须针对具体协议分别确认有效授权，不从本记录推导运行权限。

以下变化需重新审查受影响部分：引入上游运行依赖、改变 Jazzy/Core 发行版、修改五类契约或 SafetyState 语义、绕过 ActionBuffer/软件门控/MCU 边界，或把 mock 证据扩展为模型/物理执行结论。
