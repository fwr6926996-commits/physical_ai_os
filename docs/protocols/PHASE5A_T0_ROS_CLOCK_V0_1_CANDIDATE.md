# Phase 5A T0-ROS 时钟负向测试与 Mock 失效处理候选

Protocol ID: `P5A-T0-ROS-0.1`

Status: `DESIGN_CANDIDATE_NOT_ACCEPTED_NOT_AUTHORIZED`

Date: 2026-10-28（Asia/Shanghai）。这是 Gate T0 的补充实验设计，不是 Gate R 的功能闭环验收。

实验分类候选：有界功能资格验证；配置保持固定，单个场景只改变预先列出的时钟状态/控制序列或证据副本故障。当前尚非可执行资格快照。

## 目标与当前边界

T0-L 已接受固定合成时间逻辑；T0-H 正式12/12及本机来源绑定已有工程证据，**T0-H结果的人类接受仍待明确记录**。现有正式suite均不重跑。
本候选补实际rclpy/TimeSource/use_sim_time路径：ROS时间未初始化、暂停、回拨或切换来源时，native动作有效期及明确的失效处理是否仍可核查。
当前只完成设计和只读来源清点；没有启动ROS context、节点、DDS、strace测试或本协议suite。

不修改系统时间，不创建真实控制话题，不接相机、模型、MCU、舵机或设备驱动。Mock命令只写文件。完整Observation/PolicyOutput消息、ACT动作块、QoS积压、ActionBuffer并发、Gate R/C/PR与RT0留给原后续Gate。

## 原理与本次关键判断

`use_sim_time=false`时，ROSClock可返回system来源的读数；启用后跟随TimeSource收到的`/clock`。第一条时钟消息到达前可为0，暂停后读数可以不再前进；回拨有jump通知。不能用这条时间线代替host monotonic动作TTL。[ROS Clock and Time](https://design.ros2.org/articles/clock_and_time.html)

本机已安装的`rclpy/clock.py`要求jump callback短且不阻塞；`time_source.py`把参数变化和clock消息接到ROSClock。需分别证明：

1. **时钟事件已发生并被观察到**：来自真实TimeSource/jump callback，而非输入向量声称有reset。
2. **执行端已提交失效处理**：关闭本地mock输出许可、移除pending token、作废旧session，并写`INVALIDATION_COMMIT`。
3. **提交之后的停止证据完整**：检查实际命令文件、计数、进展和终点。jump日志本身不等于执行端已停止输出。

ROS时钟事件通过有界本地管道传到native执行端。发布时刻、callback时刻、执行端commit时刻之间存在通信/调度间隔；本步记录这些间隔内的命令，不把提交后的零输出扩张成“发布回拨瞬间全系统已停”。

## 进程与解释器

| 所有者 | 候选解释器 | 职责 |
|---|---|---|
| supervisor/离线复核 | 既有Conda Python3.13 | manifest、脚本步骤、BOOT/namespace核对、BOOTTIME守卫、证据复核 |
| ROS clock worker | `/usr/bin/python3` 3.12 | 同一进程内clock_driver和clock_probe两个测试node，实际rclpy TimeSource及jump callback |
| native mock executor | 既有Conda Python3.13 | HOST_STEADY采样、单个pending token、原TimeJudge、输出门控和Mock sink |
| 受控strace辅助进程 | 已安装`/usr/bin/strace` | ROS worker的网络/文件访问记录；不附着现有其他进程 |

当前rclpy扩展为CPython3.12 ABI，system Python默认环境没有jsonschema；不把3.13 site-packages加入3.12，不安装新依赖。ROS worker使用本地ROS setup解析出的**独立子进程环境**；native worker保持3.13环境。两边只交换有界JSON，TimeJudge/Schema保持既有只读来源。
supervisor→strace→ROS worker的受控父子链和supervisor→native worker分别记录PID/starttime/boot/time namespace。不能直接套用旧T0-H“worker的直接parent必为supervisor”的条件。

本轮最多4个受控进程同时存活，DDS线程另记；不运行ros2 CLI或daemon，不并行启动多个场景。R01…R07每场景使用新的受控进程上下文；R08…R10只生成R04证据的标记副本。

## ROS与传输配置候选

- ROS Jazzy，固定`RMW_IMPLEMENTATION=rmw_fastrtps_cpp`；当前包rclpy7.1.11、rcl9.2.11、rmw_fastrtps8.4.4、Fast DDS2.14.6，运行前重新冻结实际身份。
- `ROS_DOMAIN_ID=91`；使用唯一namespace `/t0_ros_<规范化run_id>/`。TimeSource的绝对`/clock`通过node remapping指向本run的`.../clock`，禁止写全局控制话题。
- `ROS_AUTOMATIC_DISCOVERY_RANGE=SYSTEM_DEFAULT`，将发现配置交给固定XML；清除子进程继承的ROS_STATIC_PEERS/ROS_LOCALHOST_ONLY/ROS_DISCOVERY_SERVER及其他FastDDS profile覆盖项。不修改用户shell或全局环境。
- `FASTRTPS_DEFAULT_PROFILES_FILE=<冻结XML>`，`RMW_FASTRTPS_USE_QOS_FROM_XML=0`，`RMW_FASTRTPS_PUBLICATION_MODE=SYNCHRONOUS`。XML仅提供127.0.0.1 UDPv4，关闭builtin transports和multicast discovery，initial peer为127.0.0.1；DataSharing沿用该版本RMW的OFF设置。
- 选择SYSTEM_DEFAULT是为了让固定XML生效：8.4.4的LOCALHOST分支会追加SHM和UDP transport，不能据一个LOCALHOST环境标签声称“只有回环UDP”。[8.4.4源码与配置说明](https://github.com/ros2/rmw_fastrtps/tree/8.4.4)
- 两个node关闭rosout、远程parameter services和logger service；允许框架的parameter_events及discovery元数据。参数通过受控进程内API设置。发现非本run节点或clock publisher时，停止，不自动换domain重试。
- publisher与TimeSource subscription均为KEEP_LAST/depth1、BEST_EFFORT、VOLATILE；以实际endpoint读回为准。本机TimeSource源码是该subscription配置依据，不推导成全项目QoS建议。
- ROS worker使用SingleThreadedExecutor和默认MutuallyExclusiveCallbackGroup；probe和driver各自node。rclpy无本项目C++ intra-process配置；DDS同进程优化是否发生不作为本步通过条件。此处不验证跨ROS进程DDS数据路径。

`loopback_udp_v0_1_candidate.xml`当前只做XML结构核查，尚未由FastDDS解析/运行验证。开发及正式运行均用受控strace核对ROS worker的IP发送目标和profile/共享内存访问；只允许127.0.0.1的IPv4 UDP流量，以及本地只读NETLINK接口查询。不得出现SHM/data-sharing产物、外部IP发送、TCP/IPv6数据传输或XML加载错误。配置与观测不符即停；不自动切换transport、改系统网络或申请扩权继续。
strace启动/ptrace受限、记录丢失或地址无法判定时，属于预检/证据不足，不能判隔离通过。trace含全部本run ROS线程，追踪辅助进程也计入进程数；不附着现有其他进程，不作性能比较。

## 时钟与失效处理

动作观察/生成/消费/输出检查仍由`clock_gettime_ns(CLOCK_MONOTONIC)`产生。BOOT/namespace绑定沿用T0-H原则；CLOCK_BOOTTIME只作守卫。ROS_TIME单独记录source、clock_type、active状态和clock_epoch，绝不与native绝对值相减。
ROSClock即使处于system fallback也保留其逻辑类型与来源状态，不凭数值大小改标HOST_STEADY。active但未收到clock时，把raw_ros_ns=0保留在诊断记录中，将对应契约时间点标INVALID/null，不把0当新鲜观察。

probe保留jump handle，注册`min_forward=None`、`min_backward=Duration(nanoseconds=-1)`、`on_clock_change=True`。真实callback只读取其TimeJump参数和native测量点，递增本地事件号并写入固定64槽内存ring；不在callback里再次调用同一个ROSClock.now，不阻塞写文件/管道、不等待远端。ring满置loss标志，整场停止。主循环排出原始记录并通知supervisor。

每个控制步骤记录请求ID、publish尝试、probe实际读数/active状态、jump marker、supervisor转发和executor接收/提交。clock_step最多500ms；同一步可每20ms最多重发25次相同clock值以等待实际观测，全部尝试记录。未观测到目标值或目标callback时停止，不自动重跑场景、不修改预期。

在READY之后的回拨、ROS_TIME_ACTIVATED/DEACTIVATED均触发失效通知。执行端使用短操作`ENQUEUE`、`TICK`、`INVALIDATE`和`REARM_ONCE`：
- 初次配置时尚无active执行session，事件仍记录，许可保持关闭；首次ARM只能在绑定、有效clock观察和证据就绪后由supervisor分配初始session。配置事件不偷偷产生执行许可。
- INVALIDATE提交时先关本地许可，移除pending token，将当前执行session标失效，记录原因、token、旧session、检查时刻、buffer前后状态和命令计数；不能只由观察进程报警。
- 不在TICK中sleep等到期；supervisor用native守卫驱动短tick并优先转发已收到的失效事件，避免单个RPC阻塞通知处理。本步不证明任意并发竞争或硬实时优先级。
- 无自动恢复。仅R06允许在manifest预先列出的条件满足后REARM_ONCE：有有效ROS时钟观察、来源核对完整、新session由supervisor分配、旧token已作废；再生成新token。
- 旧session拒绝不能被EXPIRED掩盖；目标检查前要求旧token数值上仍未到期，否则SETUP_TIMING_NOT_MET并停。

回拨场景使用明确的测试协调：先正常输出一条baseline命令；再ENQUEUE一个仍有效的token，记录TEST_HOLD_CONSUMPTION，触发实际ROS事件，收到INVALIDATION_COMMIT后再请求消费旧token。该设计检验确定的失效处理路径，不宣称完成并发ActionBuffer竞争测试。baseline与hold记录均保留，不能从一开始永远禁止输出来凑“零命令”。

## 十个场景

| ID | 实际步骤 / 证据 | 固定预期 |
|---|---|---|
| R01 | 独立环境/传输/endpoint检查；use_sim_time=false、实际ROSClock inactive读取 | 配置可核查；许可未开放；0命令；不计算跨域年龄 |
| R02 | 真实set_parameters_atomically启用use_sim_time；尚未发布clock | 参数成功、active=true、raw_ros_ns=0；INVALID/null；保持关门且0命令 |
| R03 | 实际观察clock=1s后发一条正常baseline命令；创建200ms TTL token，暂停clock发布 | ROS时间保持1s，native仍到期；EXPIRED；停止窗内命令增量0、过期计数增量1 |
| R04 | 观察2s→1s的真实回拨及negative jump；baseline+hold旧token | marker与提交关联；关门/清pending/旧session失效；提交后实际停止窗命令增量0 |
| R05 | 已armed时真实use_sim_time true→false | 读回false/inactive，DEACTIVATED事件及失效提交齐全；0条提交后命令 |
| R06 | 先在active=true且clock=2s时armed，再false→true；观察重新启用时的缓存值，再发布3s并显式一次rearm | DEACTIVATED/ACTIVATED均记录；启用不自动重开；缓存2s不冒充新观察；3s实际确认后新session拒绝旧未到期token，仅新token可输出 |
| R07 | 使用实际ROSClock读数构成明确标记的负向域输入，与native时间点混合，无映射 | CLOCK_DOMAIN_MISMATCH，age=null；0命令，不称动作过期 |
| R08 | R04已采集记录副本移除jump marker，保留缺口 | EVIDENCE_INCOMPLETE，不推断已停 |
| R09 | R04副本移除INVALIDATION_COMMIT或窗口终点（固定为移除commit） | EVIDENCE_INCOMPLETE，不推断已停 |
| R10 | R04副本在提交后窗口插入命令，相关序号/计数一致更新 | FAIL_MOCK_STOP_WINDOW_ONLY；保留异常命令证据 |

R08…R10为POST_COLLECTION_VERIFIER_FIXTURE，不重放实际执行；原日志不可变，副本逐事件成帧。R07是实际ROS读数驱动的契约负例，不把它说成执行端误接错误时钟后仍安全运行。
R07必须把实际ROS source按ROS_TIME登记，再与已登记native点混合；否则UNKNOWN_CLOCK_SOURCE会掩盖要检验的CLOCK_DOMAIN_MISMATCH。
R02使用新建TimeSource的首次启用；R06沿用同一TimeSource，其本地源码保留last_time_set，故不能预期每次重新启用都会回到0。R06缓存值为2s，目标新观察为3s，分别记录，不能重标缓存值为新采集。

## 停止与独立证据

动作TTL为200ms，旧session反例TTL为2s，合成Observation Age上限5s；仅为测试条件。每个停止窗至少200ms，20ms一个slot共10个；记录实际tick并要求落在各自slot内，不补写missed tick。
R03窗口起于实际EXPIRED之后；R04/R05窗口起于INVALIDATION_COMMIT之后。窗口起止均重新采native时间。保留窗口之前的baseline命令，检查窗口内实际命令记录和首尾计数**增量**，不能要求整份文件为空或用一个“已停止”字符串替代。

独立验证器从关闭的文件核对来源/解释器/endpoint、原始clock步进、真实callback、控制关联ID、buffer清除、session轮换、拒绝记录、tick slots、loss=0、连续序号、计数与命令。单独列出publish→jump observed→invalidation commit各区间内的命令；时刻不同源时不发布时差。
sink前重采样并保留写入完成包络；若写入完成晚于有效期，不删除命令，判SINK_COMPLETION_AFTER_DEADLINE。未知来源、丢失控制消息、ring溢出、退出不完整或trace缺失均停止，保留部分证据。

拟需产物：run_manifest.json、环境/动态库/传输profile哈希、endpoint读回、clock_publish/probe/jump记录、control与executor事件、mock_commands.jsonl、network/file trace、verifier_fixtures.jsonl、result.json、hashes.json和REVIEW.md。

## 冻结、运行边界与结论

建议新增 `runtime_core/phase5a_t0_ros/` 与 `tests/phase5a_t0_ros/`；旧T0-L/H只读引用。使用已有软件，不装依赖、不改系统配置/权限、不删除DDS或其他进程资源。
开发范围若获批，可包括本run的ROS节点、环回UDP和strace预检，失败日志保留；正式前固定全部代码/验证器/场景/配置、两套解释器及模块/动态库、proc绑定/环境、节点/话题名生成规则、命令、授权和输出路径。
正式最多1次10场景suite，每场景一次；authorization_id级单次领取。任何非预期失败、调度前提未满足或证据不足即停，无自动重跑。
最多4个受控进程；CLOCK_BOOTTIME总守卫60s；单场景10s；单clock_step500ms；单帧16KiB，实际+副本事件合计4096条，trace最多4MiB、全产物最多8MiB。trace为原始辅助文件，事件/JSON帧上限单独执行；超限不得删日志继续。
开发产物限 `/tmp/phase5a-t0-ros-<id>/`；正式产物拟为 `artifacts/phase5a/t0_ros/<run_id>/`，ROS_LOG_DIR只指向本run目录。不复用全局ros2 daemon，不设后台服务。

本候选未授权编码、ROS/DDS节点或strace运行。若接受，可明确授权本地实现/开发及传输预检；开发检查和profile验证通过、快照冻结后一次正式suite，条件满足后无需重复索取同一授权。
若通过，最强允许结论为`T0_ROS_CLOCK_NEGATIVE_MOCK_PASS`。随后整理Gate T0覆盖矩阵，由人类单独审查；不自动写完整Gate T0 PASS，不扩张为Gate R、部署或物理安全结果。
