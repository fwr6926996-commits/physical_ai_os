"""Convert the frozen ACT ExportedProgram to OpenVINO IR and check CPU output."""

import json
from pathlib import Path

import numpy as np
import openvino as ov
import torch


PACKAGE_DIR = Path(__file__).parent / "policy_package_v1"
EXPORTED_PROGRAM = PACKAGE_DIR / "act_tensor_wrapper.pt2"
IR_PATH = PACKAGE_DIR / "act_cpu_reference.xml"
CORRECTNESS_PATH = PACKAGE_DIR / "correctness_cpu.json"


def main() -> None:
    exported_program = torch.export.load(EXPORTED_PROGRAM)
    ov_model = ov.convert_model(exported_program)
    ov_model.reshape({
        "state": [1, 6],
        "wrist_image": [1, 3, 480, 640],
    })
    ov.save_model(ov_model, IR_PATH, compress_to_fp16=False)

    core = ov.Core()
    compiled = core.compile_model(ov_model, "CPU")
    model_input = torch.load(PACKAGE_DIR / "reference_model_input.pt", weights_only=False)
    expected = torch.load(PACKAGE_DIR / "reference_output_normalized.pt", weights_only=False)["action_chunk"]

    request = compiled.create_infer_request()
    inputs = list(compiled.inputs)
    if len(inputs) != 2:
        raise RuntimeError(f"Expected two OpenVINO inputs, found: {[port.any_name for port in inputs]}")
    request.infer({
        "state": model_input["observation.state"].numpy(),
        "wrist_image": model_input["observation.images.wrist"].numpy(),
    })
    actual = request.get_output_tensor(0).data.copy()
    np.testing.assert_allclose(actual, expected.numpy(), rtol=1e-4, atol=1e-5)
    absolute_error = np.abs(actual - expected.numpy())
    correctness = {
        "device": "CPU",
        "comparison": "normalized ACT action chunk: PyTorch CPU vs OpenVINO CPU",
        "input_shapes": {
            "state": [1, 6],
            "wrist_image": [1, 3, 480, 640],
        },
        "output_shape": [1, 100, 6],
        "rtol": 1e-4,
        "atol": 1e-5,
        "max_abs_error": float(absolute_error.max()),
        "mean_abs_error": float(absolute_error.mean()),
        "status": "PASS",
    }
    CORRECTNESS_PATH.write_text(
        json.dumps(correctness, indent=2) + "\n",
        encoding="utf-8",
    )
    np.save(PACKAGE_DIR / "reference_output_openvino_cpu.npy", actual)

    print(f"Saved IR: {IR_PATH}")
    print(
        "OpenVINO inputs:",
        [(port.any_name, str(port.partial_shape), str(port.element_type)) for port in inputs],
    )
    print(
        "OpenVINO output:",
        str(compiled.output(0).partial_shape),
        str(compiled.output(0).element_type),
    )
    print("CORRECTNESS: PASS (rtol=1e-4, atol=1e-5)")
    print(
        "Error: max_abs=",
        correctness["max_abs_error"],
        "mean_abs=",
        correctness["mean_abs_error"],
    )


if __name__ == "__main__":
    main()
