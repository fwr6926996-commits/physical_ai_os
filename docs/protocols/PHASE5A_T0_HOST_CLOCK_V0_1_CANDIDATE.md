# Phase 5A T0-H 本机时钟绑定与双进程 Mock 协议候选

Protocol ID: `P5A-T0-H-0.1`

Status: `DESIGN_CANDIDATE_NOT_ACCEPTED_NOT_AUTHORIZED`

Date: 2026-10-27（Asia/Shanghai）。T0-H 是 Gate T0 的补充验证步骤，不新增正式工程 Gate。

## 当前决定与要补的证据

T0-L 0.2 已获 `ACCEPTED_T0_L_OFFLINE_MOCK_ONLY`，34 个合成场景符合预期；来源见 `experiments/EXP-2026-004_sig_a0_alignment/t0_acceptance_20261027/ACCEPTANCE.md`。
其中时间点来自命名向量，尚无实际时钟采集器。下一步建议把同源判断接到本机实际 API，并在两个本地进程间传递一个 mock token。
本候选尚未获实现或运行授权。本次只编写协议、场景及来源/环境记录；不执行双进程采样或新 suite。

本步拟验证：**受信启动上下文 → 实际采样 API → 本机进程间传递 → 消费/输出前重检 → 原始文件复核**。
保留既有 T0-L 冻结代码、Schema、输入、日志和接受记录。新适配器/runner/验证器拟放 `runtime_core/phase5a_t0_host/`，回归检查拟放 `tests/phase5a_t0_host/`。

## 为什么先做这个范围

| 路径 | 本轮取舍 |
|---|---|
| 直接实现完整 ROS 闭环 | 还需消息、动作块、QoS、回调和时间链冻结；当前 Gate T0 未完成，留给后续协议 |
| 本机真实时钟与本地管道，两个工作进程 | 本候选推荐；直接补来源绑定与进程/session 缺口，可沿用已有 Python/jsonschema，不引入 ROS 环境依赖 |
| 现在迁移 C++ 或接模型/硬件 | 不是本步验证所需；不改变 Python/ROS 功能闭环再 C++ 核心化的主线 |

本步通过仍不构成完整 Gate T0；真实 `use_sim_time`/ROS clock 跳变负向验证、ROS 时钟适配与完整消息时间链尚待后续。
T0-L 的合成跨 MCU 域拒绝记录可复用为逻辑证据，不能升级成真实 MCU 同步测试。

## 三个核心概念

1. **domain 是类别，source 是实例。** 本机进程使用同一个 Linux `CLOCK_MONOTONIC`，还要核对同一次 boot 和同一 time namespace。相同 hostname 或两边自报 `HOST_STEADY` 不足以绑定来源。Linux time namespace 可改变 monotonic 的读数基准。[Linux time_namespaces](https://man7.org/linux/man-pages/man7/time_namespaces.7.html)
2. **session 是执行代际。** 同一个时钟继续走，工作进程重启后仍可比较读数；旧动作是否允许输出是另一项检查。受信 supervisor 给新运行上下文分配新 session，旧 token 不能选择当前 session。
3. **真实采样与伪标签不同。** 建议采样器固定调用 `time.clock_gettime_ns(time.CLOCK_MONOTONIC)`，返回整数 ns；绑定信息来自本地采集和 supervisor 的独立核对。Python 提供显式 clock ID 的整数采样 API。[Python time](https://docs.python.org/3.13/library/time.html#time.clock_gettime_ns)

ROS Time 可随 `use_sim_time` 使用另一条时间线；native host 样例不验证这一行为。[ROS Clock and Time](https://design.ros2.org/articles/clock_and_time.html)

## 受信启动与来源绑定

最多同时三个进程：supervisor、producer、executor。工作进程由 supervisor 创建，使用继承的匿名 stdin/stdout 管道传递有界 JSON 帧；不创建 socket、ROS node 或 daemon。
producer/executor 启动完成并获 supervisor 的 READY 后才生成 token，启动耗时不混入本步的有效期。

拟固定下列身份：

| 项 | 来源与检查 |
|---|---|
| run_id / session_id | supervisor 在动作到达前分配，写入 manifest；不从 payload 推导 |
| boot 身份 | 只读 `/proc/sys/kernel/random/boot_id`，记录规范化值 SHA-256；不采集 machine-id |
| 时钟实例 | 明确 API 与符号/数字 clock ID；本 profile 只允许 `CLOCK_MONOTONIC`，不替换成 RAW/BOOTTIME/REALTIME |
| time namespace | 各进程实际 `/proc/self/ns/time` 的 stat(dev, ino)；supervisor 从 `/proc/<受控pid>/ns/time` 独立核对。记录 `time_for_children` 和 timens_offsets，不能只检查父进程 |
| 进程实例 | supervisor 的 Popen 身份、PID、`/proc/<pid>/stat` starttime、父子关系；PID 不是 source 的单独依据 |
| 代码/解释器 | 冻结采样器、调用路径、解释器二进制与相关依赖身份；实际路径和版本以运行前复验为准 |

source 拟为 `linux-monotonic:<sha256>`；摘要输入是带固定字段名、排序与分隔的规范 JSON：boot_id_sha256、namespace_dev、namespace_ino、clock_id_symbol。具体规范序列化随实现冻结；不把任意字典 repr 当身份。
source 不包含 session；控制上下文分别固定两者。运行前和结束前均核对绑定；不支持过程内 namespace/clock/provider 切换。
缺少 boot/namespace/进程身份、父子来源不一致或 provider 选错时，停止该场景，记录绑定拒绝、零输出与 age unavailable；不猜测同源。

采样器不得从输入字段接受 timestamp/source/session 覆盖；TimePoint 仅由固定调用路径和已核对的上下文组成。valid_until 是 generated_at + 本场景固定 TTL 的派生点，单独标为 `derived_expiry`，不伪装采样事件。
受信代码、OS 与本地进程属于本步前提；这不是对恶意本地程序的密码学认证，也不证明没有内核、虚拟化或采样器外部篡改。

## 与既有逻辑的连接

沿用 T0-L 0.2 TimePoint 的字段、int64 检查、半开有效区间和拒绝优先级；旧 Schema/实现只读引用，新目录实现适配层，不回改已验收输入。
新增的 bootstrap 绑定检查先于 TimePoint 判断，并使用独立结果字段 `binding_verdict`；不把 bootstrap 拒绝冒充原判断器的新错误码。
映射仍为空。外来 source/session/metadata 错误时，禁止年龄计算；日志不得为不可比时间发布“已过期”的结论。

每场景只有一个 pending token，executor 唯一拥有缓存；只有完成 READY、绑定核对和当前 session 检查后才有本地 mock 输出许可。这不是完整 SafetyState/MCU 许可实现。
新 token 的 Observation 是确定性合成记录：`payload_kind=SYNTHETIC_OBSERVATION_NO_SENSOR`。capture 只表示该合成记录创建时的本轮采样，不表示相机采集或历史 bag 原始时刻。
记录 capture/generated/receive/dequeue/execute_attempt；receive 单独作为事件点，不把它作为旧 TimeJudge 不支持的角色传入。首轮不报告完整 Queue Delay 或 E2E。

当前 mock 输出前只有一次性 final check。新适配器必须重新读取实际时钟，不能把 dequeue 时间复制成 sink 时间。允许场景额外记录 sink 写入完成后的时间：
- `t_sink_attempt < valid_until` 才允许开始 mock 写入。
- `t_sink_write_complete >= valid_until` 时记 `SINK_COMPLETION_AFTER_DEADLINE`，本场景不判通过；保留已写命令，不能删除它来“修正”结果。
- 两次检查之间不能证明文件写入与有效期原子化。本步报告检查及写入包络，不声称硬实时发布保证。

## 场景与非确定调度

12 个场景的固定预期见 `experiments/EXP-2026-004_sig_a0_alignment/t0_host_design_20261027/scenarios_v0_1_candidate.json`。
正常/身份负例 token TTL 拟为 2 s；H-06/H-07 到期场景 TTL 拟为 200 ms；都只是测试条件，不是控制参数建议。合成 Observation Age 上限拟为 5 s。
负向 source/session 用例执行拒绝检查前必须记录数值上尚未到期的证据；否则 `SETUP_TIMING_NOT_MET`，不能以 EXPIRED 代替目标机制，也不自动重试。
到期等待使用 actual monotonic predicate `now >= valid_until`，sleep 只用于让出 CPU；等待不足时不靠“sleep 了200ms”推断到期。H-07 必须先采到实际 dequeue 放行，再进入输出前的有界延迟。

| ID | 要验证的内容 | 结果来源 |
|---|---|---|
| H-01 | supervisor 独立核对两个 worker 来源；跨进程因果握手及未到期正常输出 | 实际 provider、管道与 sink |
| H-02 | provider 实际选择 REALTIME 却声称 HOST_STEADY | 明确标为故障 provider 配置，bootstrap 拒绝 |
| H-03 | namespace 证据与 supervisor 观察不一致 | 标为构造 metadata 故障；不真的修改 namespace |
| H-04 | 必需绑定证据缺失 | 标为采集故障注入；不 chmod 或删除系统文件 |
| H-05 | 输入伪造 source，数值仍有效 | 实际 native 基础 token 的 payload 故障；原判断器拒绝且 age=null |
| H-06 | 实际等待到期后消费 | EXPIRED、零命令、expired_drop=1及完整停止窗 |
| H-07 | dequeue 仍有效，sink 前实际到期 | 初检 ALLOW，重检 EXPIRED；完整停止窗、零命令 |
| H-08 | supervisor 关闭并等待旧 worker 退出，分配新 session 后启动新 worker；旧token仍未到期 | 原source可保持相同；旧token SESSION_MISMATCH，新token才可输出 |
| H-09 | TimePoint domain 与已绑定 source 登记冲突 | CLOCK_SOURCE_METADATA_MISMATCH，age=null，零命令 |
| H-10 | 实际停止窗副本移除一条关键事件 | 构造验证器输入，EVIDENCE_INCOMPLETE |
| H-11 | 实际停止窗副本制造 sink 计数矛盾 | 构造验证器输入，EVIDENCE_INCOMPLETE |
| H-12 | 实际停止窗副本插入一条命令并一致更新相关计数/序号 | 构造验证器输入，FAIL_MOCK_STOP_WINDOW_ONLY |

每场景一轮；H-08 的旧/新 worker 先后启动，任一时刻仍最多三个受控进程。H-10…12 使用 H-06 已采集的不可变原始记录的标记副本；不重放实际消费，也不修改 H-06 原记录。
H-01 因果证据要求 parent-before ≤ producer-read ≤ executor-read ≤ parent-after，明确各读数来自相同绑定；不以相近数值证明来源，也不把这条不等式当时钟同步精度。

## 实际停止窗口及独立复核

H-06/H-07 窗口从实际拒绝事件之后的 `WINDOW_START` 新采样起算，至少 200 ms。每20ms一个计划slot，共10个（0…180ms）；每次记录实际 tick、计划slot、迟到量、是否 empty，窗口终点重新读取实际时钟。
每slot最多计一次，不用突发补写日志伪造进展；tick实际时刻必须位于本slot的20ms区间。错过slot、重复slot、真实读数倒退或无终点判 EVIDENCE_INCOMPLETE，正式运行停止，不把主机负载问题解释成实时性合格。
这与 T0-L 的虚拟11个精确tick不同；native窗口不要求实际读数恰好等于计划时刻。

独立验证器从已关闭的实际文件复核：来源/进程/session与manifest、完整因果链、同源年龄算术、允许场景sink写入包络、拒绝记录的token/current time/valid_until/reason、单次过期计数、10个实际slot、完整终点、序号与最终记录数、loss=0、sink首尾计数及窗口内命令文件。
H-07 的过期拒绝发生在 sink attempt，停止窗内只剩空队列；必须关联拒绝及窗口前的计数基线，不能要求窗口内再次丢弃同一token。
零命令必须由命令文件和计数共同支持。H-10…12 标为 `POST_COLLECTION_VERIFIER_FIXTURE`，构造完整性拒绝或失败符合预期才是场景通过；不将它们写成真实 runtime 故障。
旧 T0-L 验证器针对固定虚拟窗口，不能直接宣称能验证 native slot 或 supervisor 来源证据；新验证器与原始日志结构需在实现后、正式运行前一起冻结。

## 资源边界、冻结与停止

- 使用已有 `/home/lucas/miniconda3/bin/python` 候选解释器及本地依赖；不安装、不激活新环境。当前只读清点见环境记录，运行时重新复验。
- 仅读取必要 boot/proc namespace/进程身份、解释器和代码；只创建受控子进程与匿名管道。无网络、socket、ROS、模型、相机、设备文件或系统配置写入。
- 不调用 clock_settime、setns、unshare，不变更 namespace 或系统时间；不测试真实 suspend/resume 或 reboot。CLOCK_MONOTONIC 不包含 suspend 时间，本结果不覆盖跨休眠动作有效性。
- supervisor 以 `CLOCK_BOOTTIME` 作独立防挂起超时守卫，最多30s，覆盖受控子进程启动到全部退出；它只用于资源守卫，禁止与MONOTONIC绝对值相减或用于动作有效期。缺该API时预检停止。
- 至多3个同时存活进程；一条JSON帧最多16KiB；实际+构造事件合计最多1024条，总产物最多2MiB；单次到期等待最多2s（BOOTTIME守卫），不忙等。
- 控制帧和证据写出都须有界；独立supervisor守卫覆盖管道满/子进程卡住，失败时只终止本run拥有且进程实例核对一致的子进程，保留部分产物。EOF、读写错误、身份变化、资源超限或非预期结果立即停止，不自动重跑。
- 开发验证可修实现并保留每次日志，不修改固定预期消除失败。正式前冻结协议、场景、采样/IPC代码、验证器、解释器/依赖、boot/namespace预检、命令、12个场景、阈值、run/session生成规则、输出路径和授权引用。
- 若之后获准条件式正式运行，开发检查通过且快照冻结后最多1次12场景suite。新run_id或重新复制freeze不恢复同一授权的正式次数；记录authorization_id级领取凭据。正式失败或场景前提不满足时停止，不复测挑选结果。
- 开发产物限 `/tmp/phase5a-t0-host-<id>/`；正式产物拟在 `artifacts/phase5a/t0_host/<run_id>/`。父进程与子进程记录由各自单写者负责，禁止共享追加导致不可判事件顺序。

拟需产物：run_manifest.json、binding_observations.jsonl、producer_events.jsonl、executor_events.jsonl、supervisor_events.jsonl、mock_commands.jsonl、verifier_fixtures.jsonl、evidence_summary.json、result.json、hashes.json、REVIEW.md和一次性授权领取记录。
只允许结论 `T0_H_NATIVE_CLOCK_AND_LOCAL_PIPE_MOCK_PASS`，不能缩写为 Gate T0 PASS。人类结果接受仍单独记录。

## 当前供人审的决定

是否接受“显式 CLOCK_MONOTONIC + boot/time namespace 独立核对 + supervisor-owned session + 本地管道”的最小补充范围？
如接受，可分别授权本地实现与开发验证，并明确是否条件式批准开发通过、冻结后的一次12场景正式suite；本候选自身不产生这些权限。
