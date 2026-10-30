# SIG A0 首轮源码对齐与 Phase 5A 学习入口

日期：2026-10-26（Asia/Shanghai）

状态：`SOURCE_REVIEW_IN_PROGRESS`。人审与 Phase 5 handoff：`NOT_RECORDED`。SIG-A0：未判 PASS。

本轮把“继续项目”推进为可复核的 Phase 5 入口材料：重验阶段资格和环境、固定五个上游仓库身份、比较核心接口，并提出无硬件的第一个闭环。
尚未安装、构建、启动 ROS 节点、执行策略或连接 DK-2500/机械臂。所有新增材料位于本目录。

## 当前事实

- 当前 HEAD：`3f141d0c444fbacea62d3d5b788980d437c95aad`，分支 `main`。
- Phase 4 关闭记录为 `PASS — CPU FP32 OFFLINE BACKEND ONLY`，`Next phase entry: ALLOWED`。这允许设计下一协议；不扩展冻结 CPU FP32 后端的准入范围。
- 执行书及两份绑定 Addenda 的 SHA-256 均与 `docs/reference/l1/README.md` 一致，具体值见 `environment_snapshot.txt`。
- 本地主机为 ThinkBook，Ubuntu 24.04.4、Jazzy、GCC 13.3、Python 3.12.3。本次 Python 进程解析的 RMW 为 `rmw_fastrtps_cpp`；已安装 Fast DDS 包版本为 2.14.6。它们不是 DK-2500 的实时环境快照，也不证明节点可运行。
- `ros2_ws` 与 `runtime_core` 下未发现实现文件。五类接口目前以治理文档约束为依据，不声称已有可编译消息定义。
- 历史 LeRobot 源环境版本只从 `software_baseline.yaml` 读取，未激活和复验；FakePolicy 首步不依赖该环境。

## 本轮证据与覆盖

| 文件 | 用途 |
|---|---|
| environment_snapshot.txt | 命令及输出、ROS/RMW/DDS 本地身份、三份上位文档哈希 |
| preserved_worktree.json | 本轮写入前已有 25 个修改/未跟踪文件的状态与 SHA-256 |
| governing_extracts.txt | 执行书 3、7、9 节及 T0/R M1/可迁移性约束；段落定位不是页码 |
| upstream_snapshot.json | 五个仓库精确 commit、23 个已获取源码/配置/许可证文件及原始 URL |
| sources/ | 固定 commit 的读取副本，只作审查证据，不是激活的依赖或可执行环境 |
| interface_mapping.md | 七项职责比较、包职责草案、首轮验证问题和学习判断 |
| component_dispositions.md | 八项组件的唯一建议处置、依据与重开条件 |

官方首页、工作组索引、2026-08-18 状态文章及两项 REP 的页面已刷新；未声称穷尽最新会议和全部 roadmap。
Jazzy Executor 网页返回 Access Denied，未把它作为已读取的技术依据。
ROS 时间原理参考 [Clock and Time](https://design.ros2.org/articles/clock_and_time.html)：ROS time 可以暂停或跳变，不能把它与另一时钟的数字直接相减。

上游 demo 使用 Lyrical/Python 3.14，SO-ARM、Feetech、Rosetta 的已阅 CI 配置分别包含 Jazzy。由此只能建议分组件审查，不能认定兼容性通过。
Feetech 的真实初始化路径含舵机参数写入与扭矩使能，因此首个闭环的执行端采用纯日志 Mock Adapter。

## 后续顺序

1. 补齐 SIG-A0 的 charter、相关工作组 roadmap 与最新官方状态覆盖；保持总预算最多两个有效工作日，未解决项写明 DEFER 和触发条件。本轮为第一个源码审查工作日，无兼容性 spike。
2. 在 Phase 5A 架构冻结前，刷新 Notion 的 `P1 / L1 + Phase 5A` 候选池和原 L2 双入口，完整读取候选要求。本轮未访问 Notion，历史候选结论不得当作当前覆盖。
3. 人审接口职责和组件处置，完成首次能力的关键判断后，记录 SIG-A0 handoff。无人工决定前保持本状态，不宣称架构已冻结。
4. 先设计 Gate T0：字段来源与测量点、clock_domain、同步状态、契约版本；审查回放时间映射。通过所需负向测试前不发布跨时钟域 E2E 数字。
5. 冻结 Phase 5A 首个本地 ReplayObservation + FakePolicy 协议：mock-only 路由、容量与覆盖、动作有效期、执行节拍、超时、最大时长、停止/清理和证据路径。参数仍待确定。
6. 按首次学习规则由用户完成一个学习关键操作；随后助手可以处理约定范围内的实现、测试与重复证据。首个 mock 闭环不等于 Gate R 完整通过；QoS/Executor/Callback Group/Lifecycle、受控阻塞/积压和 rosbag2 回放仍需后续证据。
7. mock 闭环及相关入口条件具备后，再设计变化输入/全主机链的 CPU FP32 集成协议。模型、目标身份和新实验授权独立核对。

## 学习检查

本次模式为 `LEARN`，学习深度为 `OPERATOR`：先理解职责和失效路径，不要求手写哈希、解析器或整套实现。
按仓库 `AGENT.md` Rule 1，首次重要能力需要解释原理并让用户完成关键步骤；人审不由助手代签。

只需先看这三个入口：

1. `interface_mapping.md` 的“首个闭环”和“教学用的一个判断”：动作何时允许被消费？
2. `component_dispositions.md` 的 driver/Rosetta/demos 三类差异：为什么 Jazzy CI 配置还不足以采纳整个栈？
3. `governing_extracts.txt` 的 Gate T0：为什么同一个 timestamp 类型仍可能不能相减？

关键问题：动作有效至 100 ms、120 ms 才被执行端取出时，在哪个环节拒绝它？若没有其他有效动作，模拟执行端应记录什么行为？
这个回答用于选择后续设计与用户关键操作，不是本轮工程验收或机器人运行许可。

## 结论与限制

建议首步采用项目自有 ReplayObservation / FakePolicy / 有限 ActionBuffer / 周期消费 / 软件门控 / 日志 Mock Adapter。
不引入新的上游运行依赖。完整 SIG-A0、T0、Gate R、Gate C、Gate PR、实时性和物理安全均未通过本轮取得新 PASS。
本轮没有产生已接受的阶段/候选处置决定，未变更 Notion 阶段投影或历史记录。
