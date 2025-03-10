# Edge SDK (mellerikat-edge)

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

Create the Configuration file and prepare to use it on Edge Conductor.

1. Navigate to the AI Solution folder.
2. Execute edge init to create a Configuration file.
3. Based on the Configuration information, register the Edge App with Edge Conductor.
4. After running edge init, proceed to register the Edge App with Edge Conductor and deploy the model.

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

Simply perform inference with 'edge inference'.
"edge inference" performs the following steps.
1. Download the model deployed by Edge Conductor.
2. Modify the model in train_artifact and apply the parameters set in experimental_plan.
3. Run ALO.
4. Send inference_artifacts to Edge Conductor.

**__Note__**: 'edge inference' will not be marked as connected in Edge Conductor.

```bash
edge inference --input {input_file_path}
```

---

## Example: Using the Edge App Emulator

To interact with the Edge Conductor in a manner similar to the Edge App, you can use the following Python script:

```python
import mellerikatedge.edge_app as edge_app

emulator = edge_app.Emulator('edge_config.yaml')

#========================== SDK Edge App ============================#
# Edge App registration requested.                                   #
#====================================================================#
emulator.register()

#========================== Edge Conductor ==========================#
# Register SDK Edge App                                              #
# Deploy Model #1 to SDK Edge App.                                   #
#====================================================================#

try:
    #========================== SDK Edge App ============================#
    # Download Model #1 and connect it to Edge Conductor via Websocket.  #
    #====================================================================#
    status = emulator.start()
    print("status", status)

    if status == edge_app.Emulator.STATUS_INFERENCE_READY:
        # Inference with a file (Model #1)
        if emulator.inference_file("file_path"):
            emulator.upload_inference_result()

        # Inference with a DataFrame (Model #1)
        if emulator.inference_dataframe(dataframe):
            emulator.upload_inference_result()

        #========================== Edge Conductor ==========================#
        # Deploy Model #2 to SDK Edge App.                                   #
        #====================================================================#

        #========================== SDK Edge App ============================#
        # Automatically received deployment of Model #2                      #
        #====================================================================#

        # Inference with a file (Model #2)
        if emulator.inference_file("file_path"):
            emulator.upload_inference_result()

        # Inference with a DataFrame (Model #2)
        if emulator.inference_dataframe(dataframe):
            emulator.upload_inference_result()

finally:
    #========================== SDK Edge App ============================#
    # Disconnect websocket                                               #
    #====================================================================#
    emulator.stop()

```

---

This SDK provides a flexible and powerful way to emulate Edge App functionality, making it suitable for both development and testing purposes.
