# Edge SDK (mellerikatedge)

The Edge SDK emulates the functionality of the Edge App, enabling seamless integration with the Edge Conductor. It receives model deployments from the Edge Conductor and sends inference results back, supporting both DataFrame and file-based inference. The SDK is highly customizable, making it adaptable to legacy environments.

> **Note:** The Edge SDK is ideal for end-to-end verification of AI solutions. For operational use, we recommend using the Edge App.

---

## Environment Setup

### Setting Up and Running ALO and AI Solution

1. **Install ALO**: Follow the [ALO Installation Guide](https://mellerikat.com/user_guide/data_scientist_guide/alo/alo-v3/quick_run).
2. **Develop AI Solution**: Create an AI solution tailored to your problem.
3. **Register and Train**: Register the AI Solution in the AI Conductor and train the model using the Edge Conductor.

### Install Edge SDK

```sh
pip install mellerikat-edge
```

---

## Quick Start

### Creating a Configuration

Generate a configuration file for the Edge SDK in your AI Solution folder. This file requires details about the Edge Conductor and a unique serial name to identify the Edge instance.

```bash
cd {AI_Solution_folder}
edge init
```

If successful, an `edge_config.yaml` file will be created with the following structure:

```yaml
solution_dir: /home/user/projects/ai_solution  # Path to ALO
alo_version: v3
edge_conductor_location: cloud                 # Edge Conductor environment (cloud or on-premise)
edge_conductor_url: https://edgecond.try-mellerikat.com  # Edge Conductor URL (include https or http)
edge_security_key: edge-emulator-{{user_id}}-{{number}}  # Unique key for Edge identification; replace {{ }} with appropriate values
model_info:                                    # Populated when the SDK runs and the model is deployed
  model_seq:
  model_version:
  stream_name:
```

### One-Time Inference

Perform a one-time inference using the `edge inference` command. This connects to the Edge Conductor, retrieves the inference model, updates metadata in the `experimental_plan` and `train_artifact`, and executes ALO.

```bash
edge inference --input {input_file_path}
```

---

## Example: Using the Edge App Emulator

To interact with the Edge Conductor in a manner similar to the Edge App, you can use the following Python script:

```python
import mellerikatedge.edgeapp as edgeapp

emulator = edgeapp.Emulator('edge_config.yaml')
try:
    emulator.start()
    if emulator.deploy_model():
        # Inference with a file
        if emulator.inference_file("file_path"):
            emulator.upload_inference_result()

        # Inference with a DataFrame
        if emulator.inference_dataframe(dataframe):
            emulator.upload_inference_result()

finally:
    emulator.stop()
```

---

This SDK provides a flexible and powerful way to emulate Edge App functionality, making it suitable for both development and testing purposes.
