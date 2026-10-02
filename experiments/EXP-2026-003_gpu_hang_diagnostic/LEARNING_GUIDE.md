# Stage 0 Learning Guide

## What to understand before running

The worker and supervisor have different responsibilities:

```text
Supervisor                         Worker
----------                         ------
start exact child                  announce ready
receive and save events            emit work_enter
measure time since last message    perform mock work
detect loss of progress            emit work_return
terminate only its child           emit heartbeat
write result.json                  repeat or complete
```

In the `hang` scenario, iteration 3 intentionally follows this path:

```text
work_enter(iteration=3)
-> no work_return(iteration=3)
-> no heartbeat(iteration=3)
-> watchdog timeout
-> supervisor terminates child
```

## Prediction to write down first

Before running, predict:

1. Last confirmed-good completed iteration:
2. Last event expected from the worker:
3. First event expected but missing:
4. What the watchdog result can prove:
5. What it cannot prove:

## First learning command

Run this from the repository root:

```bash
python3 experiments/EXP-2026-003_gpu_hang_diagnostic/mock_watchdog_lab.py \
  --run-id learning_hang_01 \
  --scenario hang \
  --duration-seconds 4 \
  --work-seconds 0.1 \
  --hang-after 3 \
  --watchdog-seconds 1 \
  --startup-seconds 5
```

Do not rerun if the result is unexpected. Inspect these files first:

- `experiments/EXP-2026-003_gpu_hang_diagnostic/evidence/learning_hang_01/events.jsonl`
- `experiments/EXP-2026-003_gpu_hang_diagnostic/evidence/learning_hang_01/result.json`

## Questions after the run

1. Why is iteration 2 the last completed iteration even though iteration 3 appears in the log?
2. Why does missing `work_return(3)` narrow the boundary more than a missing heartbeat alone?
3. Does the watchdog prove why the work call stopped returning?
4. If this were a real `infer()` call, which components would still remain inside the fault boundary?
