# EXP-2026-003 Stage 2E-A Offset Capture Mock Review

日期：2026-10-01  
结论：`PASS_STAGE2E_OFFSET_CAPTURE_MOCK`  
范围：普通 native busy-loop target；没有初始化 OpenVINO 或 GPU

## 1. 验证了什么

mock 在一次有界 GDB attach 中同时取得：

- worker PID 对应的主线程 LWP；
- native 顶部函数和 backtrace；
- `info sharedlibrary`；
- `info proc mappings`；
- 主线程 `pc` 寄存器；
- PC 所指向的当前指令；
- GDB 正常 detach；
- detach 后 target 仍处于 `R (running)`；
- 原 SIGTERM recovery 成功，exit code `-15`。

最终 mock 用时约 `0.149 s`，原始 GDB 输出约 `13,917 bytes`。

## 2. module offset 算法验证

本次 mock 观测值：

```text
pc                  = 0x71bb67bfc175
mapping_start       = 0x71bb67bfc000
mapping_end         = 0x71bb67bfd000
mapping_file_offset = 0x1000
module path         = libstage2e_native_mock.so
```

按协议公式：

```text
stable_module_offset
= pc - mapping_start + mapping_file_offset
= 0x1175
```

解析器同时要求 PC 只落入该 module 的一个 mapping；不能唯一对应时必须失败，不允许猜测。

## 3. 一个执行环境差异

在 Codex filesystem sandbox 内第一次调用时，GDB attach 被隔离环境阻止，质量检查失败，
但 target recovery 正常。本机权限下执行同一脚本后通过。

这说明 ptrace mock 的执行环境本身是实验条件之一。真实 preflight 必须在与最终 attempt
相同的本机权限环境中运行，不能把 sandbox attach failure 误写成产品故障。

## 4. 仍未验证什么

- 没有验证生产 wrapper 与 Stage 2D baseline 的集成；
- 没有验证 stripped `libigdrcl.so` 的实际 mapping/offset；
- 没有验证匹配调试符号或源码函数名；
- 没有验证 OpenVINO、GPU plugin、OpenCL runtime、kernel 或 GPU 的根因；
- 没有验证第二个时间点；
- 没有产生 GPU 准入证据。

## 5. Artifact hash

- `stage2e_offset_capture_mock.py`: `bd6a52c7482063866e4107533e8a903cd455c546d0e60518face4068389da681`

该 hash 只记录本次通过的 mock 版本。若后续修改脚本，必须重新运行并更新 Review。

## 6. Gate

协议设计和独立 offset mock 已通过。下一步可以实现 production wrapper 草案和对应的
无 GPU integration mock；真实 GPU Stage 2E-A 仍未获授权。
