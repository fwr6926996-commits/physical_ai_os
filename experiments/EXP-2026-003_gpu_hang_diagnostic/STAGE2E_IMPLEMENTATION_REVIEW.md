# EXP-2026-003 Stage 2E-A Implementation Review

日期：2026-10-01  
结论：`PASS_DRAFT_IMPLEMENTATION_AND_NO_GPU_INTEGRATION_MOCK`  
真实执行状态：`READY FOR ONE HUMAN-STARTED ATTEMPT`

## 1. 实现边界

Stage 2E-A production wrapper 复用冻结的 Phase 3 baseline、Stage 2D worker 和 Stage 2B
共享 infer enter/return 计数器。相对 Stage 2D，新增内容仅用于一次 timeout 后的 GDB
mapping/PC/offset 取证。

新增文件：

- `stage2e_offset_evidence.py`：GDB 命令、主线程选择、mapping 解析、offset 计算与质量分类；
- `run_stage2e_offset_capture.py`：production wrapper 草案；
- `capture_stage2e_preflight.py`：只读 preflight 草案；
- `stage2e_runner_mock.py`：production wrapper 的无 GPU integration mock；
- `STAGE2E_DRAFT_MANIFEST.json`：真实执行硬阻断。

## 2. 主线程选择修正

实现没有沿用“GDB thread 1 就是主线程”的假设。GDB helper 在 attach 后读取所有 threads，
按 Linux LWP/TID 等于 worker PID 查找并切换到主线程，然后输出显式证据标记：

```text
STAGE2E_MAIN_LWP=<worker pid>
STAGE2E_MAIN_PC=<program counter>
```

quality classifier 还会再次检查 marker 中的 LWP 与实际 target PID 相同。

## 3. offset 证据约束

完整证据必须同时满足：

1. hang baseline status 符合历史 watchdog 分类；
2. GDB helper 成功且没有 timeout；
3. 原始输出保存成功；
4. 显式主线程 LWP 与 target PID 相同；
5. GDB 正常 detach；
6. 精确 module path 的一个且仅一个 mapping 包含主线程 PC；
7. mapping 若包含权限列，必须为 executable；
8. offset 由 `PC - mapping_start + mapping_file_offset` 计算。

任一条件不足都不会产生 complete 分类。

## 4. integration mock 结果

状态：`PASS_STAGE2E_PRODUCTION_WRAPPER_INTEGRATION_MOCK`

正向控制：

- 主线程识别正确；
- raw output 保存；
- module mapping 唯一；
- stable offset 为 `0x1175`；
- GDB detach 后 target 为 running；
- 原 recovery 为 SIGTERM；
- helper 约 `0.142 s`。

负向控制：

- 错误 module path → `OFFSET_EVIDENCE_PARTIAL_MAIN_THREAD_ONLY`；
- 删除主线程 marker → `OFFSET_EVIDENCE_PARTIAL_MAPPING_ONLY`；
- raw output 写入失败 → `OFFSET_EVIDENCE_UNUSABLE_RAW_OUTPUT_NOT_SAVED`；
- 未复现 hang → `GDB_NOT_TRIGGERED_NO_HANG`；
- draft manifest → 在 OpenVINO/GPU 初始化前拒绝真实 runner。

## 5. Draft artifact hashes

- offset helper: `fe0ae2e2a4fa0e817a07b97ea2a31586fdf613684c4b06cecc4412c359a73095`
- offset standalone mock: `bd6a52c7482063866e4107533e8a903cd455c546d0e60518face4068389da681`
- production runner: `d45cf3e405948db15539a3d8cdbf6e5144c89db81b8fa46dd67def5678b01b3e`
- preflight: `1ae567ce9208d947d2b7f870d456bf52103675726f975fdd0ef53fba94577edd`
- integration mock: `5b66544893e71df652bb17d2dcef06e041458a9fa606348331c8f6cb7fcd4483`
- draft manifest: `2472058debf4b3fc4ae7133979c594d5eef1cbbf930dec7193e1262edfe8fc5f`

这些是审查用 draft hash，不是执行批准。冻结 manifest 后，runner/preflight 的 hash 必须重新
计算并形成最终 manifest。

## 6. 尚未支持的结论

- mock offset `0x1175` 与 `libigdrcl.so` 无关；
- production wrapper 通过 mock 不代表真实 hang 一定复现；
- 即使取得 `libigdrcl.so` offset，也不能单凭 offset 宣布根因；
- 真实 Stage 2E-A 不属于资格测试，不能恢复 GPU.0 准入。

## 7. Gate 决定

实现草案与无 GPU integration mock 已通过。Human owner 于 2026-10-01 明确批准一次
Stage 2E-A。最终 artifact hashes 已写入 manifest；接下来只允许生成匹配 preflight，并由
human owner 手动执行唯一一次 attempt。不得自动重试。
