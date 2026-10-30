# T0-H 0.1 设计审查交接

Status: `CANDIDATE_FOR_HUMAN_REVIEW`；无实现、构建或运行结果。

## 已有事实与待补证据

| 事项 | 已实现 | 已验证 / 接受 | 本候选要补 / 后续保留 |
|---|---|---|---|
| 同源时间与session判断 | runtime_core/phase5a_t0/logic.py 的 TimeJudge | T0-L固定合成向量34/34，已获限定接受 | 以本机实际采样取代固定数值，来源与启动上下文独立核对 |
| 时间读取入口 | 当前MockExecutor接收now参数；默认sink attempt复制now并换measurement_point | 足以验证合成检查；不证明真实sink重新采样 | 新适配层重新调用显式clock API，不修改已冻结旧代码 |
| provider身份 | 原manifest登记VIRTUAL_TEST_CLOCK | 没有真实boot/namespace/API绑定证据 | 两个worker分别采集，supervisor从proc独立核对 |
| session轮换 | 原runner通过固定context overrides构造新session | 证明逻辑拒绝旧session | supervisor实际结束/重启受控worker并分配新session；不声称自动故障恢复 |
| 停止窗口 | 原evidence.py/suite.py实现虚拟时间和原始JSONL复核 | 6个实际mock窗口，时间轴由向量驱动；每窗11tick/0命令/expired_drop=1 | 新采样时钟下200ms观察窗、10个实际tick slot；新的独立验证器 |
| 时钟跳变/ROS | 没有ROS runtime实现 | T0-L只有给定fake读数和声明reset | 实际use_sim_time/ROS clock负例仍待后续；本候选不补写通过 |
| Gate R / C / RT0 | 无完整闭环 | 未验收 | 消息/API/动作块/QoS/Executor/并发/真机等按原Gate推进 |

## 推荐的最小变化

阅读 `docs/protocols/PHASE5A_T0_HOST_CLOCK_V0_1_CANDIDATE.md` 的“受信启动与来源绑定”“实际停止窗口”即可检查关键取舍。
固定CLOCK_MONOTONIC，记录boot/time namespace，session由supervisor掌握；两个工作进程仅通过本地匿名管道传单次token，输出只有mock文件。新逻辑目录拟独立，不回改T0-L证据。

12场景分开标记真实采样路径、provider/metadata故障，以及采集后验证器副本。后者不能冒充真实系统故障。调度前提不满足、漏tick、证据丢失或超时均停止，不用自动重跑挑选结果。

不将hostname、相近时间数值或get_clock_info自报看作足够证明。源API与本地proc检查可建立受信软件环境内的来源证据，不建立对恶意进程的认证。

## 本轮检查与授权边界

本轮只进行仓库/资料/环境元数据清点和设计数据静态检查；没有创建新runtime实现，没有启动双进程时钟测试、ROS、模型或硬件，也没有重跑T0-L。
正式候选尚缺实现、开发证据、运行快照和新授权；设计snapshot不能充当运行freeze。
当前动作是未接受的设计准备，不改变已同步的接受结果或下一授权Gate；依 docs/process/NOTION_SYNC.md，本轮不触发新的工程结果投影。接受/授权之后再同步具体决定。

接受本方案时，可明确是否授权：本地实现与开发验证；开发检查通过并冻结后，执行一次12场景正式suite。接受设计、授权执行和接受结果保持可区分记录。
