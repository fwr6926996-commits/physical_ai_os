# EXP-2026-003 Stage 2E 精确源码研究

日期：2026-10-01  
性质：静态 Research；没有运行 OpenVINO/GPU，没有修改驱动、runtime 或准入状态  
上游基线：Intel `compute-runtime` release `25.18.33578.77`，tag commit `d74fef5757d1c669e173f1427ba25a25871672f8`

## 1. 为什么进行这一步

Stage 2D Round 1 已经证明：发生 `infer_enter(12397)` 后没有对应的
`infer_return`，GDB 停住进程时，主线程顶部九帧都位于已剥离符号的
`libigdrcl.so`。

这仍然只是一张“当时在哪里”的照片。静态源码研究的目的，是列出与现象相容的
候选执行机制，并明确下一份证据需要回答什么；它不能把相容性提升为根因。

## 2. 精确版本身份

- 本机包：`intel-opencl-icd 25.18.33578.77-1146~24.04`。
- 本机库 Build ID：`58ccca242c62c0629c06940ee3d7b8a40b298e35`。
- 本机库 SHA-256：`d43af828e1acfcce4a2c042167ecacb270e9356fa55a3a557f18cd55b79540da`。
- 上游 release/tag：`25.18.33578.77` / `d74fef5757d1c669e173f1427ba25a25871672f8`。
- release commit message 记录 `Source: 211cd3dd5d41fe4cdcccfb53ef9b4f73b1988e84`。
- 硬件：Intel Arrow Lake-P iGPU，PCI ID `8086:7d51`，内核驱动 `i915`。

版本号能建立“源码候选基线”，但本机二进制来自 Ubuntu/Intel 包装构建；在没有
匹配调试符号或可验证重建产物时，不能假定源码函数与未知地址已经一一对应。

## 3. 源码中的候选等待链

精确 tag 中存在以下调用关系：

```text
OpenCL Event::wait
→ CommandQueue::waitUntilComplete
→ CommandStreamReceiverHw::waitForTaskCountWithKmdNotifyFallback
→ CommandStreamReceiver::waitForCompletionWithTimeout
→ CommandStreamReceiver::baseWaitFunction
→ WaitUtils::waitFunction
```

相关源码位置：

- `opencl/source/event/event.cpp`：阻塞 event wait 调用 command queue 的完成等待；
- `opencl/source/command_queue/command_queue.cpp`：`waitUntilComplete()` 进入 CSR 完成等待；
- `shared/source/command_stream/command_stream_receiver_hw_base.inl`：先进行带参数的等待；若返回 `notReady`，执行 KMD/flush-stamp 等待后，再以关闭 timeout 的参数进行阻塞完成等待；
- `shared/source/command_stream/command_stream_receiver.cpp`：`baseWaitFunction()` 在 tag/task count 未达到目标时反复检查、下载 tag、检查 GPU hang；
- `shared/source/utilities/wait_util.h`：一次等待迭代可执行 `pause`、`tpause` 或 `umonitor/umwait`，随后 `std::this_thread::yield()`；
- `shared/source/os_interface/linux/drm_command_stream.inl`：Linux 的 flush-stamp 路径可进入 user-fence wait 或 DRM handle wait；
- `shared/source/direct_submission/linux/drm_direct_submission.inl`：direct-submission wait 也存在基于 `WaitUtils::waitFunction()` 的循环和周期性 hang 检查。

Arrow Lake 的 capability table 同时表明 CCS direct submission 具备启用能力，但
“硬件支持/默认能力”不等于本次进程一定使用该路径；还需要运行时证据。

## 4. 当前证据能支持的结论

### 已支持

1. 精确版本源码中确实存在“host 等待 GPU task count 完成”的用户态等待机制。
2. 该机制包含 `pause/yield` 等行为，因此能够形成“调用长期不返回，同时大约占用一个 CPU 核”的外观。
3. 某些 fallback 路径最终会调用没有 timeout 的完成等待，所以 application watchdog 仍然是必要的外部有界恢复机制。
4. `libigdrcl.so` 是值得优先定位的观察边界，而不是凭空猜测出来的组件。

### 尚未支持

1. Stage 2D 顶部九帧就是上述任一具体函数。
2. runtime 在等待一个永远不会完成的 GPU task、在自身 livelock，或处于其他内部路径。
3. direct submission、user fence、DRM handle wait 中哪条路径在本次进程实际启用。
4. 最初错误由 OpenVINO、GPU plugin、OpenCL runtime、kernel driver 或 GPU hardware 中哪个组件产生。
5. 修改任何 driver/runtime/debug flag 会修复问题。

## 5. 为什么 Stage 2D 地址现在不能离线符号化

Stage 2D 保存了 ASLR 后的绝对地址，例如主线程 frame 0 为
`0x00007b4b606008c6`，但没有保存同一进程的：

- `info sharedlibrary`；
- `info proc mappings`；
- `/proc/<pid>/maps` 原文；
- 与该 Build ID 匹配的调试符号。

Stage 2C 只保存了 maps 的 hash 和汇总，不包含原始 mapping。没有模块 load base 和
file offset，就不能可靠地把绝对地址换算为稳定模块偏移；猜测页对齐基址会产生伪证据。

## 6. 下一条最小可判别问题

下一阶段只回答：

> 若相同的 `infer_entered_not_returned` 再次出现，能否在一次有界快照中同时保存主线程
> PC/backtrace 与动态库 mappings，从而把 `libigdrcl.so` 的 ASLR 绝对地址转换成可供
> 上游比较的稳定模块偏移？

这叫 Stage 2E-A。它不比较两个时间点，也不改变 runtime 版本。若 Stage 2E-A 仍不足，
“双快照是否停在同一偏移”只能作为另一个需单独批准的 Stage 2E-B 问题，不能偷偷并入。

## 7. 工程决定

- Stage 2D 保持关闭，不重开 Round 2/3。
- GPU.0 保持 `CLOSED_NOT_ADMITTED`。
- Phase 3 保持 `PARTIAL PASS — CPU FP32 ONLY`。
- 先完成 Stage 2E-A 协议与无 GPU mock；真实 GPU 运行必须再次单独批准。
- 等待 Intel issue #1012 的回复不是停止条件；本地静态研究和 mock 可以并行进行。

## 8. 官方入口

- Release: https://github.com/intel/compute-runtime/releases/tag/25.18.33578.77
- 已提交上游问题: https://github.com/intel/compute-runtime/issues/1012

