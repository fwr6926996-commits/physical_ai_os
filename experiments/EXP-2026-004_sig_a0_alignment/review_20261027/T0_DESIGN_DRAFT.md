# Gate T0 与首个 mock Stage 的设计草案

日期：2026-10-27。状态：`DESIGN_ONLY_NOT_FROZEN_NOT_EXECUTABLE`。
用途：在 SIG-A0 正式交接前完成可审查的设计准备，不授权编码、构建或节点运行。

## 先建立时间的含义

时间戳是“某个时钟在某个测量点的读数”。同为纳秒、数值相近，都不能证明它们能直接比较。
第一阶段把运行间隔放在同一台主机、同一 host steady 时钟来源内。回放文件的历史时间保留为源数据，不冒充本轮的当前时间。

| 字段 | 草案语义 |
|---|---|
| timestamp | 读数与单位明确；无有效读数时显式无效，不用 0 伪装未知 |
| clock_domain | 区分 HOST_STEADY、SYSTEM_TIME、ROS_TIME、CAMERA_DEVICE、MCU_UPTIME 等类别 |
| source | 哪个时钟实例/采集源；同类别但不同主机或重启前后不能自动视为同源 |
| measurement_point | capture、receive、assembled、generated、enqueue、dequeue、execute 等具体事件 |
| synchronization_status | 同源、已有有效映射、未同步、未知应能区分；状态词汇尚未冻结 |
| contract_version | 指向本轮 schema、单位与比较规则的版本 |

同源判断还需要运行会话和时钟实例身份。拟以 run/session 及明确的 clock source 记录，是否需要单独的 clock_instance/映射代际字段，在 T0 冻结时决定。
这不等于采用外部 Temporal Trust 的完整六字段标签协议。

## 比较与恢复约束

- 同源 steady 时间用于间隔、超时、动作有效期、jitter/deadline。
- ROS/system 时间用于可读时间、回放关联和已定义的跨事件对齐，不能替代 steady 间隔。
- 跨域只有在映射、有效期、误差及重置行为有证据时才允许比较；否则拒绝计算或分段报告。
- 进程/回放重新开始后不继承上次会话的动作；旧 session 的序号不能与新 session 混排。
- 从旧 bag 转出的观测必须同时保留源时间和本轮 replay 事件；在没有映射时，不计算源 capture 到本轮 execute 的绝对 E2E。
- Action Age 与源 Observation Age 分别核对；动作刚生成不代表观测刚采集。

## 将来需要的负向验证

| 验证问题 | 测试设计草案 | 通过需要的证据 |
|---|---|---|
| wall clock 跳变 | 使用注入的 fake clock/ROS sim time；不修改操作系统时间 | steady timeout 结果不被错误 wall clock 比较改变 |
| host 与 MCU 未同步 | 只构造标记为不同来源的时间样例；无需 MCU | 直接相减明确拒绝，没有伪 E2E 数字 |
| 回放暂停/重启 | mock replay clock 暂停、回拨并切换 session | 旧观测/旧动作不会凭新发布时刻重新有效 |
| 有效期边界 | 同源样例检查到期前、恰好到期、到期后 | 半开区间方案的判定一致；边界规则需预先冻结 |
| 观测旧但动作新 | 保持旧 capture 来源，再产生新 generated_at | 两类 age 不混淆；无映射时标未知或拒绝 |

这些测试尚未实现或运行，不构成 T0 PASS。

## mock Stage 的最低证据设计

正常路径建立 Observation→PolicyOutput→ActionBuffer→软件门控→Mock Adapter 的事件关联。
异常路径采用 `LEARNING_CHECK.md` 的八条约束，重点核对到期拒绝、窗口内零命令、观察者仍有进展，以及日志丢失时不能判 PASS。
动作块长度、周期、有效期、队列容量/覆盖和恢复规则必须在后续协议中明确，不能从教学例子自动取值。
首轮命令 sink 仅写测试产物，不向真实 ROS 控制 topic 或串口转发。

## 可审查的建议部署职责

以下是 SIG-A0 交接建议；尚未固定 `.msg` 或 C++ API。

| 责任 | 建议所有者 | 受保护边界 |
|---|---|---|
| ROS 数据契约 | 项目 physical_ai_msgs | 五类契约唯一，禁止厂商/舵机私有类型泄漏 |
| Replay 与观测有效性 | observation_runtime 的 replay/assembly 节点 | 保留来源、时钟与缺帧证据 |
| FakePolicy 生产者 | policy_runtime 内独立 policy producer 进程 | 不把故意延迟放进执行端的同一串行循环 |
| 有限 ActionBuffer 与消费 | policy_runtime 内单独 action executor 进程 | executor 唯一拥有缓存；接收回调与消费同步、容量和块替换规则待协议冻结 |
| 软件许可和命令过滤 | executor 输出路径内 SafetyFilter；safety_bridge 仅提供 mock 状态边界 | 每次输出前校验；禁止仅由独立观察节点事后报警 |
| Mock Adapter | executor 内日志 sink | 不加载真实驱动、不使能舵机 |
| RuntimeMetrics | 各生产/消费点产生事件，runtime_monitor 汇总 | 不用汇总节点的接收时刻冒充源事件；记录通道有界且可判丢失 |
| 组合和退出 | bringup | 全部 mock/replay；退出清理和恢复规则先冻结 |

独立进程的选择旨在隔离首轮耗时推理回调与执行循环，不声称 CPU、内存带宽或调度资源已隔离。
本地 DDS 队列与应用 ActionBuffer 是两层机制，需要分别记录。具体 QoS、Executor、Callback Group、Lifecycle 与进程间退出检测留到可执行协议，不借本表跳过 Gate R 要求。
