# SIG A0 续审与待签交接决定

日期：2026-10-27（Asia/Shanghai）。状态：`SOURCE_REVIEW_COMPLETE_PENDING_HUMAN_HANDOFF`。
SIG-A0 最终结论：`NOT_ACCEPTED_YET`。人类架构交接决定：`NOT_RECORDED`。

本轮完成有界源码审查的剩余资料覆盖与候选双入口核对，并记录动作过期/停止证据的理解检查结果。建议保留项目自有契约，以 mock/replay 进入 T0 与首个 offline Stage 的协议设计。
本文件是 10/26 首轮审查的续篇；原文件、快照及校验清单保持原样，原文中“未访问 Notion”等描述仅适用于 10/26 当轮。

## 已完成的工作

- 用户能说明消费时复查有效期、无有效动作停止模拟输出、以连续命令记录验证停止。理解检查通过的范围和原答见 [LEARNING_CHECK.md](LEARNING_CHECK.md)，不重复同一轮问答。
- charter、五个工作组页面及较新可发现官方状态已刷新；来源和检索限制见 [OFFICIAL_SOURCE_REVIEW.md](OFFICIAL_SOURCE_REVIEW.md)。这是两个有效工作日的有界审查，本轮广泛上游检索到此结束。
- 统一池当前精确筛出 19 条 P1/L1 候选，逐条读取字段与正文；原 L2 四项存量候选同时核对，见 [CANDIDATE_TRIGGER_REVIEW.md](CANDIDATE_TRIGGER_REVIEW.md)。无候选自动转成立项或采纳。
- 本地主机、HEAD、ROS 包版本、RMW 与无 Runtime 实现文件的状态已重新核实，见 `environment_refresh.json`。仍未连接 DK-2500，未激活 LeRobot/模型环境。
- 把用户回答转成后续协议的停止窗口、事件关联、过期计数和证据缺失处理要求；时间字段、比较规则、负向测试及职责安排见 [T0_DESIGN_DRAFT.md](T0_DESIGN_DRAFT.md)。

## 建议正式接受的 SIG-A0 交接内容

1. 继续采用 `SIG-aware, SIG-independent`；Core 维持 Ubuntu 24.04 / ROS 2 Jazzy。
2. 不引入上游运行依赖。保留 10/26 `component_dispositions.md` 的八项建议：SO-ARM、Feetech、Rosetta、native buffers/REP-0157、REP-0158 与 Agentic 延后；SIG demos 与 policy execution 仅作参考。所有延后项按原表的触发条件重开。
3. 五类项目契约及 InferenceBackend、有限 ActionBuffer、SafetyFilter→MCU 许可/急停边界继续由项目拥有；设备与厂商私有转换不得越过 Adapter/Backend。
4. 首个设计目标为 ReplayObservation→FakePolicy→有限 ActionBuffer→周期消费→软件门控→日志 Mock Adapter。建议 producer 与 executor 分进程，缓存唯一由 executor 拥有；具体消息/API、动作块、QoS 与调度规则仍在下一协议中冻结。
5. 先完成 T0 的时钟语义和测试协议设计，再冻结首个本地 offline mock Stage。当前交接不授权编码、构建、ROS 节点运行、模型集成或物理执行。

这里的交接接受的是上游对齐的处置和下一步职责边界，不代表 Phase 5A 架构细节已全部冻结，也不通过 T0 或 Gate R。

## SIG-A0 条款核对

| 条款 | 本轮证据与状态 |
|---|---|
| 审查源码候选具有精确身份 | 10/26 upstream_snapshot.json 固定五个仓库 commit、23 个文件；不追随浮动 main |
| Jazzy/Lyrical 与依赖差异明确 | 原接口矩阵、组件处置和 pixi/package/CI 文件；完整依赖闭包未验证，因无运行依赖采纳而不形成准入 |
| 接口与执行矩阵无隐藏假设 | 原 interface_mapping.md 和 T0_DESIGN_DRAFT.md 明列已知、缺口及待冻结项 |
| 每个组件只有一个处置 | 原组件表八项均有唯一建议，待人类接受；没有 ADOPT_AND_PIN / ADAPT_BEHIND_BOUNDARY |
| 采纳/适配组件的可复现证据 | 本轮无此类组件；未构建/运行，不能声称兼容性通过 |
| 包、时间、安全职责明确 | T0_DESIGN_DRAFT.md 规定项目所有者、独立 producer/executor、缓存所有权、输出路径软件门控与事件来源 |
| 无第二套接口或数据真相源 | 上游文件只在 evidence 的 sources/ 保存；未置入活动 workspace |
| 延后项有明确触发条件 | 原 component_dispositions.md 及本轮 19+4 候选矩阵；无任意延期扩展任务 |
| 人类理解并接受交接 | 理解检查已通过“动作过期与停止证据”部分；整个 SIG-A0 交接决定尚未收到，不能代签 |

## 执行与状态边界

| 项目 | 当前状态 |
|---|---|
| 只读资料核对、本地证据整理、设计草案 | 已在当前续推范围内完成 |
| 动作过期与模拟停止证据的理解检查 | 通过，仅限文本判断 |
| SIG-A0 human handoff | 等待明确决定 |
| T0 schema 与 mock 协议 | 草案，未冻结/未执行 |
| 编码、构建、ROS 节点/模型运行 | 本轮未开展，不由文本回答自动授权 |
| 串口、舵机、MCU、固件、驱动、系统依赖 | 本轮未访问或修改 |
| Notion | 只读；无已接受阶段决定或新执行授权，本轮不写投影 |

## 人类决定记录

待收到对上方五项交接内容的明确决定后，再如实记录原话、日期及限定范围。
当前用户关于“过期动作和停止证据”的回答只作为理解检查，不能被解释为已批准全部架构或实验。

协议依据：`docs/protocols/SIG-A0_UPSTREAM_ALIGNMENT_REVIEW.md` Acceptance criteria 要求：
“the human owner can explain the selected architecture and approve the Phase 5 handoff.”
因此助手可以准备全部可评审材料，但最终交接须由 human owner 作出；这不是工具或环境故障。
