## Edge SDK (mellerikatedge)
- It emulates the operation of the Edge App, receives the model deployment from the Edge Conductor, and sends the inference results back to the Edge Conductor
- Inference can be performed directly by handling DataFrame or files.
- Can be customized and utilized to fit legacy environments.

*__Note:__* The Edge SDK can be used for end-to-end verification of AI solutions, and for operational purposes, it is recommended to use the Edge App.


## Environment Setup
### Setting Up and Running ALO and AI Solution
1. Install ALO. ([ALO Installation Guide](https://mellerikat.com/user_guide/data_scientist_guide/alo/alo-v3/quick_run))
2. Develop AI Solution to solve the problem.
3. Register the AI Solution in the AI Conductor and train the model in the Edge Conductor.

### Install Edge SDK
```sh
pip install mellerikatedge
```


## Quick Run

### Creating a Configuration
Create a configuration file for the Edge SDK in the AI Solution folder. It requires information about the Edge Conductor and a serial name to distinguish the Edge.
```bash
cd {AI Solution folder}
edge init
```

If it operates correctly, the edge_config.yaml file will be created.

```yaml
solution_dir: /home/user/projects/ai_solution # ALO Path
alo_version: v3
edge_conductor_location: cloud # Environment of Edge Conductor (cloud or on-premise)
edge_conductor_url: https://edgecond.try-mellerikat.com # URL of Edge Conductor (include https or http)
edge_security_key: edge-emulator-{{user_id}}-{{number}} # Unique key to identify Edge, fill in {{ }} with appropriate values
model_info: # Will be filled in when the SDK runs and the model is deployed
  model_seq:
  model_version:
  stream_name:

```

### One-time Inference
A one-time inference can be executed using the edge inference command in the command line. This command connects to the Edge Conductor to retrieve the inference model, updates the meat information and input file information in the experimental_plan, updates the model information in the train_artifact, and then executes the ALO.

```bash
edge inference --input {input file path}
```

## Example of Using Edge App Emulator
To utilize the connection with the Edge Conductor in various ways, similar to the Edge App, you can write the script as follows.

```python
    import mellerikatedge.edgeapp as edgeapp

    emulator = edgeapp.Emulator('edge_config.yaml path')
    try :
        emulator.start()
        if emulator.deploy_model():
            #inference file
            if emulator.inference_file("file_path"):
                emulator.upload_inference_result()

            # inference dataframe
            if emulator.inference_dataframe(dataframe):
                emulator.upload_inference_result()

    finally:
        emulator.stop()
```