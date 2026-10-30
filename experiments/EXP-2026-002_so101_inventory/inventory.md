# EXP-2026-002 — SO-101 Inventory

## Basic Information

- Date: 2026-07-30
- Host: ThinkBook
- OS: Ubuntu 24.04
- LeRobot version: 0.6.0
- LeRobot source: `/home/lucas/lerobot`
- Conda environment: `lerobot`
- Feetech SDK: verified
- Serial permission: `dialout` verified

## Stable Port Mapping

### Leader

- USB serial by-id:
  `/dev/serial/by-id/usb-1a86_USB_Single_Serial_5B3D045278-if00`
- Kernel device during this test:
  `/dev/ttyACM0`
- `lerobot-find-port` result:
  `/dev/ttyACM0`
- Ordinary user readable:
  yes
- Ordinary user writable:
  yes

### Follower

- USB serial by-id:
  `/dev/serial/by-id/usb-1a86_USB_Single_Serial_5B3D043066-if00`
- Kernel device during this test:
  `/dev/ttyACM1`
- `lerobot-find-port` result:
  `/dev/ttyACM1`
- Ordinary user readable:
  yes
- Ordinary user writable:
  yes

## Port Mapping Conclusion

Use stable `/dev/serial/by-id/` paths in project configurations.

Do not permanently rely on `/dev/ttyACM0` or `/dev/ttyACM1`,
because their numbering may change after reconnecting the devices.

## Power Audit

### Leader

- Power supply output:
- Motor model:
- Motor rated voltage:
- Control board input marking:

### Follower

- Power supply output:
- Motor model:
- Motor rated voltage:
- Control board input marking:

## Cameras

- Camera model:
- USB identification:
- Video devices:
- Selected video device:

## Current Gate Status

- [x] LeRobot v0.6.0 installed
- [x] Feetech SDK installed
- [x] Leader port identified
- [x] Follower port identified
- [x] Stable by-id paths recorded
- [x] Serial permissions verified
- [ ] Power specifications verified
- [ ] Camera identified
- [ ] Existing calibration files inspected