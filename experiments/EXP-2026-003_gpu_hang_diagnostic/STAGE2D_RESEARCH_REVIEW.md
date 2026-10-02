# EXP-2026-003 Stage 2D 后续研究审查

日期：2026-09-30  
性质：只读 Research；没有安装、升级、降级或再次运行 GPU  
输入：Stage 2D Round 1 本机证据、已安装包信息、Intel/OpenVINO 官方 GitHub 资料

## 1. 研究问题

Stage 2D 已经把失去进展的位置从笼统的同步 `infer()` 缩小到：

```text
OpenVINO Runtime
→ Intel GPU Plugin
→ Intel OpenCL Compute Runtime (libigdrcl.so)
```

本轮 Research 要回答的不是“能否凭调用栈宣布根因”，而是：

1. 当前精确版本是否存在可确认的同类已知问题；
2. 单核接近 100% 与 `libigdrcl.so` 顶层栈能支持什么机制判断；
3. 是否已有足够依据直接修改环境或设计下一轮 GPU 实验；
4. 下一份最有价值的证据是什么。

## 2. 本机事实基线

- OpenVINO：`2026.3.1-22476-759c5a6ab8c-releases/2026/3`。
- GPU：Intel Arc iGPU (`GPU.0`)。
- OpenCL Runtime 包：`intel-opencl-icd 25.18.33578.77-1146~24.04`。
- 实际库：`/usr/lib/x86_64-linux-gnu/intel-opencl/libigdrcl.so`。
- Build ID：`58ccca242c62c0629c06940ee3d7b8a40b298e35`。
- 库 SHA-256：`d43af828e1acfcce4a2c042167ecacb270e9356fa55a3a557f18cd55b79540da`。
- 该库已剥离符号；本机包源中没有找到与该 Build ID 匹配的调试符号。
- Round 1 在第 12,397 次同步调用中出现 `enter` 而没有 `return`；watchdog 观察时进程约占用一个 CPU 核。
- 单次 GDB 快照的主线程顶部 9 帧位于 `libigdrcl.so`，但该次快照没有保存 shared-library base address / mappings。

## 3. 精确版本资料

Intel 官方 `compute-runtime` 仓库存在 `25.18.33578.77` release，release 页面给出的源提交为 `211cd3dd5d41fe4cdcccfb53ef9b4f73b1988e84`（tag commit `d74fef5`）。这与本机包的上游版本号精确对应。

当前公开检索没有找到一个同时满足下列全部条件的已知问题：

- `25.18.33578.77`；
- Linux；
- 本机这代 Arc iGPU；
- OpenVINO FP32 同步单请求；
- `infer()` 不返回；
- 单核接近 100%；
- 顶层栈位于 `libigdrcl.so`。

因此，当前结论是 **没有找到公开的精确匹配项**，而不是“已证明不存在已知问题”。公开 GitHub 之外仍可能有 Intel 内部问题记录。

## 4. 相似报告及其证据边界

### A. OpenVINO #37736：同版本下 GPU 调用不返回并占用一个 CPU 核

相似点：

- OpenVINO `2026.3.1`；
- Intel Arc iGPU；
- GPU 调用间歇性不返回；
- 观察到一个 CPU 核接近 100%；
- 上游也无法在另一台机器上稳定复现。

关键差异：

- Windows，而本机是 Linux；
- OpenVINO GenAI `LLMPipeline.generate()`，而本机是普通同步 `InferRequest.infer()`；
- INT8 MoE/offload 大模型，而本机是 FP32 小模型；
- 驱动栈和模型路径不同。

可支持：OpenVINO 2026.3.1 的 Intel GPU 路径中，确实存在公开报告的“调用不返回 + 单核忙”的故障形态，并且不复现一次不能否定历史故障。

不可支持：两个案例是同一个 bug，或本机故障来自 GenAI、INT8、MoE/offload。

### B. compute-runtime #726：`libigdrcl.so` 路径中的 100% CPU 卡住

相似点：

- Linux Intel OpenCL Runtime；
- 应用卡住；
- CPU 高占用；
- profiling 样本落在 `libigdrcl.so` 和 `sched_yield`。

关键差异：

- 2024 年的 `24.09/24.13` runtime；
- Arc A770、Fedora/容器、不同内核；
- `clpeak` / `llama.cpp`，不是本机 OpenVINO 模型；
- 没有证据表明其指令位置与本机顶部帧相同。

可支持：`libigdrcl.so` 内部轮询或 yield 可以形成“调用不返回时仍占满一个 CPU 核”的外观。

不可支持：本机一定发生了同一种循环。

### C. compute-runtime #363：等待 GPU 完成时的 busy wait

Intel runtime 的历史讨论明确展示过 `waitForCompletionWithTimeout` 中使用 `yield/pause` 等待 GPU 完成，从而让 CPU 使用率接近一个核心。

可支持：高 CPU 不等于正在完成有用计算，也不等于 Python 无限循环；它可能是 runtime 等待 GPU 的策略。

不可支持：本机顶部 9 个未知帧就是该函数；也不能区分正常短暂轮询、异常长时间轮询、livelock 或 GPU 没有完成。

### D. compute-runtime #976：接近版本的 OpenVINO → `libigdrcl.so` 故障

相似点：

- Linux、OpenVINO GPU Plugin、FP32；
- `25.18.33578` 版本族；
- 故障位置进入 `libigdrcl.so`。

关键差异：

- `25.18.33578.15`，不是本机 `.77`；
- N97/Gen12LP，硬件不同；
- 多请求、多主机线程、高吞吐；
- 结果是 SIGSEGV，而本机是单请求调用不返回。

可支持：相近 runtime 版本族的 OpenVINO 路径确实出现过公开的 native runtime 缺陷报告，且只有解析为稳定模块偏移后才能落到具体函数。

不可支持：本机也是 `makeNonResident()`、use-after-free 或同一竞态。

## 5. 为什么现在仍不能宣布根因

当前证据是一张“停止时的照片”：它证明拍照瞬间主线程位于 `libigdrcl.so` 多帧调用链中，但不能说明它在 15 秒内是否一直停留在相同指令，也不能说明最先发生错误的组件在哪里。

仍缺少：

1. 与本机 Build ID 精确匹配的符号，或从匹配源码构建出的可验证符号映射；
2. `info sharedlibrary` / `info proc mappings`，用于把 ASLR 绝对地址转换为稳定模块偏移；
3. 时间维度证据，用于区分持续停在同一位置与在 runtime 内部持续运行；
4. 能一次只改变一个变量的对照，例如严格冻结其他条件的 runtime 版本 A/B；
5. GPU/内核侧证据，用于判断 host runtime 是在等待正常完成、等待永远不会到来的完成，还是自身循环。

因此最强结论仍是“观测位置已缩小”，不是“责任组件已证明”。

## 6. 路由决定

### 立即执行方向：准备上游问题材料（不提交）

现有材料已经足以形成一份高质量的 Intel/OpenVINO 上游问题草稿：

- 最小且可重复的 FP32 同步推理路径；
- 多次历史复现；
- 精确版本、Build ID、哈希和硬件身份；
- `enter/return` 边界；
- 完整原生线程栈；
- 有界 watchdog 与恢复；
- 明确列出不能支持的结论。

上游问题应询问：

1. Build ID `58cc...8e35` 是否有可获得的匹配调试符号；
2. 该版本是否存在与长时间 OpenCL completion wait / spin 相关的内部已知问题；
3. Intel 希望下一次捕获哪些低扰动证据。

在用户确认前，不公开提交任何 issue。

### 后续候选实验：暂不执行

只有在 Research 或上游反馈给出明确可判别问题后，才设计下一阶段。例如：

- **符号化快照**：回答顶部未知帧属于哪些函数；
- **有界双快照**：回答相隔短时间是否仍是同一稳定偏移；
- **runtime 版本 A/B**：回答在严格冻结其他变量时，故障率是否随 runtime 版本改变；
- **GPU/内核侧有界采样**：回答 host 正在等待什么完成条件。

这些是不同问题，不能在一次实验里全部改变。

## 7. Gate 与工程决定

- Stage 2D 保持关闭；Round 2/3 继续禁止。
- GPU.0 保持 `CLOSED_NOT_ADMITTED`；Research 不等于重新准入。
- Phase 3 保持 `PARTIAL PASS — CPU FP32 ONLY`。
- 不因相似公开报告而升级、降级或替换 runtime。
- 不因找不到精确公开 issue 而把问题归因给硬件、OpenVINO、GPU Plugin 或 OpenCL Runtime 中任一单独组件。

## 8. 本轮 Research 结论

外部资料提高了“Intel OpenCL Runtime 内部等待/轮询路径值得优先调查”的合理性，但没有把它提升为已证实根因。

最合理的下一步不是再次盲跑，而是先把现有证据整理成上游问题草稿并请求匹配符号/诊断建议；若之后需要新实验，必须由一个明确的、可判别的问题驱动，并重新冻结方案和审批。

## 9. 官方资料

- Intel compute-runtime `25.18.33578.77` release: https://github.com/intel/compute-runtime/releases/tag/25.18.33578.77
- OpenVINO issue #37736: https://github.com/openvinotoolkit/openvino/issues/37736
- Intel compute-runtime issue #726: https://github.com/intel/compute-runtime/issues/726
- Intel compute-runtime issue #363: https://github.com/intel/compute-runtime/issues/363
- Intel compute-runtime issue #976: https://github.com/intel/compute-runtime/issues/976
