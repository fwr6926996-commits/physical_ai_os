#!/usr/bin/env bash

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${ROOT}/experiments/EXP-2026-001_environment"

mkdir -p "${OUT}"

{
  echo "========================================"
  echo "Physical AI OS - Environment Snapshot"
  echo "========================================"
  echo "Time: $(date --iso-8601=seconds)"
  echo

  echo "### Operating System"
  uname -a
  command -v lsb_release >/dev/null && lsb_release -a
  echo

  echo "### CPU"
  lscpu | grep -E \
    'Model name|Socket|Core|Thread|CPU\(s\)|Architecture' || true
  echo

  echo "### NVIDIA"
  command -v nvidia-smi || true
  nvidia-smi \
    --query-gpu=name,driver_version,memory.total \
    --format=csv,noheader 2>/dev/null || true
  echo

  echo "### Intel OpenCL"
  command -v clinfo || true
  clinfo -l 2>/dev/null || true
  echo

  echo "### ROS 2"
  echo "ROS_DISTRO=${ROS_DISTRO:-NOT_SOURCED}"
  command -v ros2 || true
  command -v colcon || true
  ros2 doctor --report 2>/dev/null || true
  echo

  echo "### Python Packages in Current Interpreter"
  python3 - <<'PY'
import importlib.metadata as metadata

for package in ("torch", "lerobot", "openvino", "physicalai"):
    try:
        print(f"{package}: {metadata.version(package)}")
    except metadata.PackageNotFoundError:
        print(f"{package}: not installed in current Python")
PY
  echo

  echo "### OpenVINO Devices in Current Interpreter"
  python3 - <<'PY'
try:
    import openvino as ov
    print("OpenVINO:", ov.__version__)
    print("Devices:", ov.Core().available_devices)
except Exception as exc:
    print("Unavailable:", type(exc).__name__, str(exc))
PY
  echo

  echo "### Conda"
  command -v conda || true
  command -v conda >/dev/null && conda env list || true
  echo

  echo "### Zephyr"
  command -v west || true
  west --version 2>/dev/null || true
  echo

  echo "### Build Tools"
  git --version || true
  cmake --version | head -n 1 || true
  gcc --version | head -n 1 || true
  g++ --version | head -n 1 || true
  python3 --version || true
} | tee "${OUT}/full_environment.txt"

{
  echo "Time: $(date --iso-8601=seconds)"
  echo "OS: $(lsb_release -ds 2>/dev/null || uname -s)"
  echo "Kernel: $(uname -r)"
  echo "ROS_DISTRO: ${ROS_DISTRO:-NOT_SOURCED}"
  echo "Python: $(python3 --version 2>&1)"
  echo "Git: $(git --version 2>&1)"
  echo "CMake: $(cmake --version 2>&1 | head -n 1)"

  if command -v nvidia-smi >/dev/null; then
    echo "NVIDIA: $(nvidia-smi \
      --query-gpu=name,driver_version,memory.total \
      --format=csv,noheader 2>/dev/null)"
  else
    echo "NVIDIA: unavailable"
  fi

  if command -v west >/dev/null; then
    echo "Zephyr west: $(west --version 2>&1)"
  else
    echo "Zephyr west: unavailable in current terminal"
  fi
} | tee "${OUT}/summary.txt"
