# SIG A0 组件处置建议

日期：2026-10-26。状态：`PROPOSED_NOT_ACCEPTED`。每个组件只有一个建议处置；无组件获得运行时准入。
精确源码身份、文件入口和原始 URL 见 `upstream_snapshot.json`。

| 组件 | 建议处置 | 已有依据与缺口 | 重新评估的触发条件 |
|---|---|---|---|
| ros2_so_arm | DEFER | 已阅工作流包含 Jazzy；SO-ARM101 launch 默认 mock，控制配置可作映射依据。未构建、未验证本项目动作/夹爪映射，资产许可证未全面核对 | 首个项目 mock 闭环完成，且确有 ros2_control mock 适配问题需要用独立 spike 回答 |
| feetech_ros2_driver | DEFER | 工作流包含 Jazzy/Humble/Rolling；真实初始化路径会写参数和使能扭矩。源码阅读不能证明硬件安全，也未完成 shutdown/recovery 审查 | 单独硬件/安全协议、映射和许可链齐备；兼容性构建仍优先在无硬件隔离环境进行 |
| Rosetta | DEFER | 工作流配置 Jazzy，样例展示 topic/contract 与回放映射；其相机、shape、关节、hold 和时间语义未与本项目契约对齐，关联仓库未全部固定 | 项目 Observation/T0 契约明确，出现需验证的 bag→Observation 边界问题；冻结关联仓库后做离线契约对照 |
| SIG demos | REFERENCE_ONLY | 固定身份下的 pixi.toml 使用 Lyrical/Python 3.14，pai.repos 有独立组件 pins；与本地 Jazzy/Python 3.12 不同 | 若拟成为运行依赖，重新做兼容性、边界及 ADR 审查；当前只参考组合方式 |
| ros2_policy_execution_pipeline | REFERENCE_ONLY | README 描述阶段式插件与按 timer 串行 update，core 公开类型依赖 Ort::Value；不能据此替代厂商无关 Backend 与解耦 ActionBuffer | Phase 5B 比较推理放置、并发及 custom Runtime/ros2_control；若拟采用，先审查公开类型与失败语义 |
| native buffers / REP-0157 | DEFER | 官方页面讨论内存布局及低开销消息；当前没有本项目拷贝/序列化瓶颈测量 | profiling 证明瓶颈影响已冻结指标，另立可行性协议 |
| REP-0158 / OpenUSD | DEFER | 官方页面现标 Accepted，范围是仿真资产互操作；本次未验证具体工具链 | Technical Core 与 Employment Gate 后，E3 需要跨仿真资产时再评估 |
| Agentic / ROS MCP | DEFER | ADR-0002 将其置于 E5；首个 Phase 5A 闭环不需要 agent 控制 | E5 正式开启且权限、安全与审计边界明确 |

CI 配置包含某发行版，只能证明工作流配置意图；本轮没有核验相应 run 结果，也没有本地构建证据。
独立审查的 default-head commits 与 demo 的 pai.repos pins 不完全一致，不能组合成“已测试整栈”。

建议当前保留项目自己的五类契约、时钟与安全所有权。任何 ADOPT_AND_PIN / ADAPT_BEHIND_BOUNDARY 均需协议要求的构建、失败、恢复、回滚和学习证据。
本表是待人审的建议；登记、源码阅读、处置建议与正式采纳分别记录。
