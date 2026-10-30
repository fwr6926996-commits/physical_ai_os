# T0-L 0.2 有界结果接受

Decision ID: `P5A-T0-L-02-ACCEPT-20261027-01`

Date: 2026-10-27（Asia/Shanghai）

Human decision: `ACCEPTED_T0_L_OFFLINE_MOCK_ONLY`

用户在上一条已展示正式34/34、26项回归检查、6个实际mock停止窗和结果边界后回复：

> 接受

本决定接受 run_id `T0-L-20261027-01` 的 `T0_L_LOGIC_AND_MOCK_EVIDENCE_PASS` 有界结果，以及已展示证据支持的时间/身份判断、消费及sink前到期拒绝、一次性mock token、过期计数去重和停止观察窗复核。构造故障证据仅支持验证器负例处理，不作为实际命令输出。

正式结果34/34符合冻结预期；26项回归检查通过。实际采集190条事件、2条允许场景命令；6个实际mock停止窗各11次tick、0条命令、expired_drop=1。已有原始日志、正式结果、冻结快照、审阅及哈希清单均保留原样；其中 PENDING 是运行/审阅时的历史状态，当前人类接受以本决定为准。精确已接受文件SHA-256见 accepted_scope_snapshot.json。

完整 Gate T0 仍为 `NOT_ESTABLISHED`。实际时钟绑定、真实跳变检测、ROS跨进程/队列集成、并发ActionBuffer、模型、相机、硬件、RT0及物理停止不在本次接受范围。

本次正式suite授权已使用一次，不重跑。本决定允许继续解释既有证据及设计、审查下一份有界集成协议；不增加新的编码、构建、节点运行、模型或硬件执行授权。后续运行须具备对应协议、冻结条件与有效授权。

仓库事实源：t0_implementation_20261027/REVIEW.md、run_freeze.json、raw_audit.json 及 artifacts/phase5a/t0/T0-L-20261027-01/。本接受记录独立附加，不回写冻结证据。
