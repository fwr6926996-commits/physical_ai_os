# Development Host Split

## ThinkBook — Ubuntu 24.04

Responsibilities:

- SO-101 and LeRobot
- RTX 5060 model training
- Intel Core Ultra and OpenVINO deployment
- ROS 2 Jazzy and C++ Runtime
- MuJoCo control simulation
- RuntimeMetrics and system integration

## Mac

Responsibilities:

- Zephyr west workspace
- STM32 firmware development and build
- MCU flashing and low-level debugging
- Project planning, documentation and code review

## Integration Boundary

The final system boundary is:

ThinkBook ROS 2 Runtime
→ UART or CAN
→ STM32 + Zephyr Safety Runtime
→ safety state and hardware supervision
