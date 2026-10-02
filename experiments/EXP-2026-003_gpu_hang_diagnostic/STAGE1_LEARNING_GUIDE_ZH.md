# Stage 1 中文阅读指南

这一步不是为了马上找出“谁坏了”，而是把真实 GPU 推理停止时的现场保存下来，供下一步判断。

## 从 Stage 0 到 Stage 1

Stage 0 的模拟事件：

- `work_enter(3)`：准备开始第 3 次模拟工作。
- 缺少 `work_return(3)`：第 3 次模拟工作没有返回。

Stage 1 把它替换成真实推理事件：

- `infer_enter(sequence=N)`：程序即将进入第 N 次 `request.infer(...)`。
- `infer_return(sequence=N)`：第 N 次 `request.infer(...)` 已经返回。
- 有 `infer_enter(N)`、没有 `infer_return(N)`：只能说明同步推理调用在观察时间内没有返回。

这个结果不能直接说明 OpenVINO Runtime、Intel GPU Plugin、i915 驱动或 GPU 硬件中的哪一层是根因。

## 四类证据分别回答什么

1. `events.jsonl`
   - 回答：最后完成的是哪次推理，哪次进入后没有返回。
   - 不能回答：`infer` 内部具体卡在哪一层。

2. `python_stack.txt`
   - 回答：超时时 Python 线程停留在哪个 Python 调用位置。
   - 如果显示停在 `request.infer(inputs)`，只能把边界缩小到 Python 正在等待原生推理调用。
   - 不能单独证明原生调用内部哪一层有错。

3. `proc_snapshot.json`
   - 回答：进程和线程当时的状态、内核等待位置等操作系统可见信息。
   - 它可能帮助区分“正在运行、睡眠等待、等待某个内核对象”等状态。
   - 一个等待位置通常只是线索，不自动等于根因。

4. `kernel_journal.txt`
   - 回答：测试期间内核是否报告 GPU hang、reset、i915 错误等信息。
   - 如果没有相关日志，只能说“没有观察到内核报告”，不能证明驱动和硬件无故障。

## 本轮固定规则

- 只运行一次。
- 只增加观察能力，不改变模型、精度、OpenVINO、驱动、内核或性能提示。
- 最长测量 180 秒；连续 15 秒没有新事件就保存现场并结束子进程。
- 如果没有复现，不自动重跑，也不恢复 GPU.0 的部署资格。
- Phase 3 仍然是 `PARTIAL PASS — CPU FP32 ONLY`。

## 运行前应该能回答

1. 为什么 `infer_enter(N)` 后缺少 `infer_return(N)` 不能证明是驱动故障？
2. 为什么 Python 栈、进程快照和内核日志需要一起看？
3. 如果本轮没有复现，为什么不能说 GPU.0 已经稳定？

