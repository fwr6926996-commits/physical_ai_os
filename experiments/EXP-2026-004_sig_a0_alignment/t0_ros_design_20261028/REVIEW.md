# T0-ROS 0.1 设计交接

Date: 2026-10-28（Asia/Shanghai）

Status: `DESIGN_CANDIDATE_FOR_HUMAN_REVIEW`；无ROS节点、DDS或本协议测试结果。

## 已有证据与本次补充

| 能力 | 当前可支持的事实 | 本候选要补 |
|---|---|---|
| TimePoint/有效期规则 | T0-L固定合成输入34/34已获限定接受 | 规则保持只读引用，不回改旧预期 |
| 本机真实时钟/进程session | T0-H正式12/12工程结果、独立原始文件复核；结果的人类接受仍PENDING | 本轮只补同步，不推定人类接受 |
| ROS clock/use_sim_time | 已读安装源码和包/ABI；没有项目运行证据 | 实际参数启停、TimeSource、clock数据与jump callback |
| 事件→执行端失效 | T0-H只有supervisor显式重启换session | 分别记录实际ROS事件、桥接通知、执行端INVALIDATION_COMMIT |
| 停止证明 | T0-H已有native真实slot与命令复核 | 有baseline命令情况下核对提交后命令增量；不得用jump日志替代执行证据 |
| ROS传输配置 | 已阅版本8.4.4源码与本机头文件/库身份 | profile需FastDDS实际解析及系统调用证据；静态XML解析不证明隔离 |

## 先理解的三个取舍

1. ROS时间暂停，不应让native动作TTL一起暂停。到期由实际CLOCK_MONOTONIC判断；两条时间线保留各自来源，不相减。
2. 回拨通知与执行端提交失效是两个事件。提交之后的完整停止窗可以证明本步的Mock拒绝；不能由一个jump通知宣称全系统在发布回拨时已停。通知前后的命令都要保留。
3. 重新启用use_sim_time可能恢复TimeSource保留的旧值。R02首次启用时的0与R06重新启用时的缓存2s是不同场景；只有3s新观察确认并明确rearm后才允许新session输出，不自动恢复旧动作。

用户要审查的关键选择是：**回拨/时间来源切换使已armed的执行session失效；恢复需要显式新session和新的观察确认，不等待ROS时间“追平”而自动恢复。** 用户不需要手写Schema、解析器或采集脚本。

## 环境与传输的实质差异

本机rclpy为Python3.12扩展；已有TimeJudge/jsonschema环境为Python3.13。采用分进程与有界JSON，避免混用ABI，也不为本步安装依赖。
版本8.4.4的LOCALHOST路径会追加SHM和UDP transport。因此候选交由固定XML约束127.0.0.1 UDPv4，用SYSTEM_DEFAULT避免ROS覆盖该profile；这一选择仍需实际trace验证，不能由配置标签推导已生效。
strace辅助进程计入最多4进程边界。此处允许的是本run受控ROS测试与回环UDP，超出了旧T0-H“只有匿名管道、无socket”的授权；必须单独授权后才能实施/预检/运行。

## 本轮产物与状态

- `docs/protocols/PHASE5A_T0_ROS_CLOCK_V0_1_CANDIDATE.md`：范围、恢复选择、十场景、配置和停止规则。
- `scenarios_v0_1_candidate.json`：R01…R10固定设计预期；runtime_results=null，不冒充已执行。
- `loopback_udp_v0_1_candidate.xml`：候选传输文件，仅结构检查，尚无FastDDS运行验证。
- `source_review.json` / `environment_inventory.json`：来源范围、当前安装文件哈希、解释器差异与未验证项。
- `host_notion_sync_resolution.json`：T0-H阶段页回读与当前P1补同步证据；旧outage/pending文件作为历史保留，现行registry已解决对应两个PENDING记录，其他13条保留。

当前没有新runtime/test目录，没有启动ROS、DDS或strace目标，也没有复跑T0-L/H。下一步缺少T0-H有界结果的人类决定，以及本候选的设计/实施/开发和条件式单次运行授权。
若获准，开发通过、传输profile验证通过并冻结之后，最多一次10场景正式suite。最强结果仅为T0_ROS_CLOCK_NEGATIVE_MOCK_PASS；之后才整理完整Gate T0覆盖矩阵供人审。
