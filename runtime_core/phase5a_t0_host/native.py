"""Explicit native sampling and local process identity; no ROS or hardware."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import time

FRAME_LIMIT = 16384
TOTAL_LIMIT = 2097152
EVENT_LIMIT = 1024


def mono():
    return time.clock_gettime_ns(time.CLOCK_MONOTONIC)


def guard():
    return time.clock_gettime_ns(time.CLOCK_BOOTTIME)


def identity(pid=None, provider="CLOCK_MONOTONIC"):
    pid = os.getpid() if pid is None else pid
    base = Path(f"/proc/{pid}")
    stat = (base / "stat").read_text().rsplit(")", 1)[1].split()
    namespace = (base / "ns/time").stat()
    return {"pid": pid, "ppid": int(stat[1]), "process_starttime": stat[19],
            "boot_id_sha256": hashlib.sha256(Path("/proc/sys/kernel/random/boot_id").read_bytes().strip()).hexdigest(),
            "namespace_dev": namespace.st_dev, "namespace_ino": namespace.st_ino,
            "time_namespace": os.readlink(base / "ns/time"),
            "children_time_namespace": os.readlink(base / "ns/time_for_children"),
            "timens_offsets": (base / "timens_offsets").read_text(),
            "clock_id_symbol": provider, "clock_id_value": getattr(time, provider),
            "sampling_api": "time.clock_gettime_ns"}


def source_id(binding):
    fields = {key: binding[key] for key in
              ("boot_id_sha256", "namespace_dev", "namespace_ino", "clock_id_symbol")}
    encoded = json.dumps(fields, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return "linux-monotonic:" + hashlib.sha256(encoded).hexdigest()


def binding_reason(reported, observed, supervisor):
    required = set(observed)
    if not required <= reported.keys() or any(reported[k] is None for k in required):
        return "BINDING_EVIDENCE_UNAVAILABLE"
    if (reported["sampling_api"] != "time.clock_gettime_ns" or
            reported["clock_id_symbol"] != "CLOCK_MONOTONIC" or
            reported["clock_id_value"] != time.CLOCK_MONOTONIC):
        return "BINDING_PROVIDER_MISMATCH"
    for key in ("namespace_dev", "namespace_ino", "time_namespace", "children_time_namespace", "timens_offsets"):
        if reported[key] != observed[key] or observed[key] != supervisor[key]:
            return "BINDING_NAMESPACE_MISMATCH"
    for key in ("pid", "ppid", "process_starttime", "boot_id_sha256"):
        if reported[key] != observed[key]:
            return "BINDING_PROCESS_OR_BOOT_MISMATCH"
    if observed["ppid"] != supervisor["pid"] or observed["boot_id_sha256"] != supervisor["boot_id_sha256"]:
        return "BINDING_PROCESS_OR_BOOT_MISMATCH"
    return None


class NativeClock:
    def __init__(self, context, binding):
        self.context, self.binding = deepcopy(context), deepcopy(binding)
        if binding["clock_id_symbol"] != "CLOCK_MONOTONIC" or source_id(binding) != context["control_clock_source"]:
            raise ValueError("clock provider/context mismatch")

    def sample(self, measurement_point):
        return {"contract_version": "phase5a.t0.timepoint/0.2-candidate", "timestamp": str(mono()),
                "unit": "ns", "clock_domain": "HOST_STEADY", "source": self.context["control_clock_source"],
                "measurement_point": measurement_point, "synchronization_status": "SAME_SOURCE",
                "session_id": self.context["session_id"], "validity": "VALID"}


def wait_until(target, limit_ns=2000000000):
    deadline = guard() + limit_ns
    while True:
        now = mono()
        if now >= target:
            return now
        if guard() >= deadline:
            raise TimeoutError("EXPIRY_WAIT_GUARD")
        time.sleep(min((target - now) / 1e9, 0.005))


def line(record):
    payload = (json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n").encode()
    if len(payload) > FRAME_LIMIT:
        raise RuntimeError("FRAME_LIMIT")
    return payload


class Journal:
    def __init__(self, path, case_id, instance_id, role):
        self.path, self.case_id, self.instance_id, self.role = path, case_id, instance_id, role
        self.sequence = 0
        self.file = Path(path).open("xb")

    def emit(self, kind, **data):
        record = {"case_id": self.case_id, "instance_id": self.instance_id, "role": self.role,
                  "sequence": self.sequence, "type": kind, "provenance": "COLLECTED_NATIVE_MOCK", **data}
        self.file.write(line(record))
        self.file.flush()
        self.sequence += 1
        if self.sequence > EVENT_LIMIT:
            raise RuntimeError("EVENT_LIMIT")
        return record["sequence"]

    def close(self):
        self.file.close()
