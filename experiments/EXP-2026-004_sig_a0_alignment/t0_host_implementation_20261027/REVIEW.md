# T0-H 0.1 本机时钟与双进程 Mock 结果审阅

Date: 2026-10-27（Asia/Shanghai）

Engineering result: `T0_H_NATIVE_CLOCK_AND_LOCAL_PIPE_MOCK_PASS`，正式12/12符合冻结预期。

Human result acceptance: `PENDING`；完整 Gate T0：`NOT_ESTABLISHED`。

用户回复“好的，接受”承接此前明确列出的 T0-H 设计接受、本地实现/开发验证、开发通过并冻结后一次12场景suite。授权 ID 为 `P5A-T0-H-01-AUTH-20261027-01`，原文与已审输入哈希见 AUTHORIZATION.json。该回复是设计与实施授权，不提前记为对本次运行结果的接受。

## 实现与验证

新增 runtime_core/phase5a_t0_host/，包含显式 CLOCK_MONOTONIC 整数采样、boot/time namespace/进程实例绑定、supervisor-owned session、producer/executor匿名管道、消费与sink前重检、Mock文件输出、有界资源守卫和独立磁盘证据复核。旧 T0-L 实现与验收证据未改。

父进程从 /proc/<受控pid>/ 独立读取 namespace、进程starttime和父子关系，结合boot摘要核对worker报告；源码冻结的采样器固定调用clock_gettime_ns(CLOCK_MONOTONIC)。source摘要规范为JSON字段排序、逗号/冒号无空格、ensure_ascii=True后SHA-256；source不包含session。身份核对失败时不进入READY，不产生动作。

每个worker实例独占raw/<instance>/events.jsonl；executor独占该实例的mock_commands.jsonl。全部关闭后由supervisor单写者合并根目录事件/命令文件。不存在跨进程并发追加同一个证据文件。

26项回归检查通过，覆盖时钟/context绑定、namespace或provider伪装、进程starttime、过期等待守卫、实际slot规则、缺记录/计数冲突/错误来源、管道帧上限和authorization级单次领取。

开发共3轮：第一轮在H-12构造验证器输入写出时触发FRAME_LIMIT并停止；该轮原始失败日志保留。原因是把完整窗口副本装入一条JSON帧。修复为逐事件/命令记录并添加副本起止和计数，保留原16KiB上限及所有场景预期。第二、三轮均12/12；最后一轮与冻结代码身份相同。

开发完成后冻结协议、12场景、源码/验证器/测试/原Schema、已有解释器及依赖身份、boot/namespace预检、启动命令、session生成规则、阈值和输出位置。冻结记录 run_freeze.json。正式run_id=`T0-H-20261027-01`，authorization级领取记录为 P5A-T0-H-01-AUTH-20261027-01.attempt.json；正式只执行1次，没有重跑。

## 人审的三个关键事实

| 对象 | 原始证据支持的结果 |
|---|---|
| H-01 来源与正常传递 | 两个worker的来源在启动和结束均经parent独立核对；producer生成与executor接收token一致；parent-before ≤ generated ≤ dequeue ≤ parent-after；正常命令在有效期内写入完成。因果顺序不被解释为时钟同步精度。 |
| H-07 sink前实际到期 | dequeue时Action Age=3.423278ms，初检ALLOW；实际等待后sink采样Action Age=200.117186ms，超过200ms TTL，重检EXPIRED；实际命令=0，expired_drop=1。停止窗200.147789ms，10个实际tick slot齐全，首尾计数为0，序号/终点/loss=0完整。 |
| H-08 重启与旧token | 旧producer/executor全部退出后才启动新worker，分配新session；source保持相同。旧token数值上尚未到期，因SESSION_MISMATCH拒绝且没有输出；新session的新token才产生一条命令。此处是supervisor显式重启，不证明自动故障恢复或真实replay跳变检测。 |

H-06消费时到期，随后实际停止窗为200.098198ms，10个tick slot、零命令、expired_drop=1。H-06/H-07均记录token编号、当前检查点、valid_until、EXPIRED及过期计数；拒绝发生在窗口之前，与窗口baseline关联，没有在每个空tick重复丢弃。

H-02/H-03/H-04分别识别错误provider配置、构造namespace metadata冲突和必需证据缺失，均未READY、无命令；H-05/H-09在数值仍有效时拒绝source/domain伪装，age=null。H-03不是实际切换namespace实验，H-04未修改系统文件。

H-10/H-11/H-12是H-06不可变原日志的标记副本：分别判EVIDENCE_INCOMPLETE、EVIDENCE_INCOMPLETE、FAIL_MOCK_STOP_WINDOW_ONLY。构造命令不在真实mock_commands.jsonl中，不把验证器负例当作运行故障。

## 证据与边界

正式证据目录：artifacts/phase5a/t0_host/T0-H-20261027-01/。20个先后运行的worker实例、40条来源观察；进程生命周期重算最多3个本run进程同时存活（supervisor+2 workers），全部worker退出。

事件逻辑计数343条；含合并副本的物理JSONL记录482行；最大一行2531 bytes；全部输出450802 bytes。未触发1024条/16KiB单帧/2MiB总量/30s守卫边界。CLOCK_BOOTTIME守卫记录只用于资源约束，不形成实时性或性能准入。

audit_raw.py只用stdlib读取正式产物，独立重算哈希、事件/命令/年龄、tick slot、拒绝计数、子进程生命周期及未到期旧session场景；raw_audit.json记录PASS。该审计没有启动worker或重跑suite。

本结果支持当前受信Linux/Python环境下的实际HOST_STEADY采样与本地进程绑定、明确session代际、管道关联和Mock拒绝/停止证据。它不是恶意进程认证或完整OS镜像证明；未验证跨namespace运行、休眠/重启恢复、ROS clock/use_sim_time负例、DDS/QoS/Executor、完整ActionBuffer并发、模型/相机/硬件或物理停止。

当前允许审阅既有证据、解释机制及设计下一份ROS时钟负例/有界集成协议。结果接受由Human Owner决定；完整Gate T0、Gate R/C/PR、RT0均未因此通过。新运行须有对应协议与有效授权，本次正式授权不能复用。
