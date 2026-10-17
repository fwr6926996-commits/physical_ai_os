# SIG-A0 Initial Component Dispositions

Status: `ACTIVATION_BASELINE`

These are conservative activation-time dispositions. They may change only after the named evidence
is reviewed. No item is admitted as a runtime dependency.

| Candidate | Snapshot identity | Disposition | Evidence or trigger |
|---|---|---|---|
| `ros-physical-ai/demos` | `ea931a9fc58de19d9c9bea0fc7dc99da1f30274b` | `REFERENCE_ONLY` | Compare composition, simulation and test patterns; never import it as a second architecture |
| `ros2_so_arm` | `e166df9d51f43b24da9b99047c6c51c306bda74f` | `DEFER` | Reconsider after manifest review and a separately approved Jazzy mock-only build question |
| `feetech_ros2_driver` | `18aed7fb26d3e2b4c0b47762f39d8698b7032422` | `DEFER` | Reconsider after lifecycle, failure, shutdown and non-bypass mapping; no hardware required |
| `iblnkn/rosetta` | `294136dc435a040d608d9efd773d70ae0b421d00` | `DEFER` | Reconsider after offline topic/QoS/timestamp/hold contract mapping and dependency pin review |
| `ros2_policy_execution_pipeline` | `9e3478a948be4ea327d43e375a51e9b535c02b0c` | `DEFER` | Root license is unresolved; also requires ownership, timing and shutdown review |
| REP-0157/native buffers | dated official REP page | `DEFER` | Trigger only after a measured copy or serialization bottleneck exists |
| REP-0158/OpenUSD conventions | official page observed as `DRAFT` | `DEFER` | Route to the later E3 simulation-asset review |

No component is currently `ADOPT_AND_PIN` or `ADAPT_BEHIND_BOUNDARY`.
