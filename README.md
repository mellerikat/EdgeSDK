## Edge SDK (mellerikatedge)
- Provides the ability to connect to the EdgeApp Emulator on the Edge Conductor, deploy the inference model, and execute it.
- Inference can be performed directly by handling DataFrame or files.
- Can be customized and utilized to fit legacy environments.

*__Note:__* The Edge SDK can be used for end-to-end verification of AI solutions, and for operational purposes, it is recommended to use the Edge App.


## Environment Setup
### Setting Up and Running ALO and AI Solution
1. Install ALO. ([ALO Installation Guide](https://mellerikat.com/user_guide/data_scientist_guide/alo/quick_run))
2. Deploy the AI solution stream you want to use on Edge Conductor to ALO.
3. Run ALO with a simple dataset to download the necessary assets and install Python modules.

### Installing Edge SDK
Download and install the `mellerikatedge whl` file from the `dist` folder.

```sh
wget https://github.com/mellerikat/EdgeSDK/raw/refs/heads/v1.0.0/dist/mellerikatedge-1.0-py3-none-any.whl
pip install mellerikatedge-1.0-py3-none-any.whl
```

### Creating a Configuration File for Edge SDK
Create a file named emulator_config.yaml at a location of your choice with the following content:

```yaml
alo_dir: /home/user/projects/alo # ALO Path
alo_version: v3
edge_conductor_location: cloud # Environment of Edge Conductor (cloud or on-premise)
edge_conductor_url: https://edgecond.try-mellerikat.com # URL of Edge Conductor (include https or http)
edge_security_key: edge-emulator-{{user_id}}-{{number}} # Unique key to identify Edge, fill in {{ }} with appropriate values
model_info: # Will be filled in when the SDK runs and the model is deployed
  model_seq:
  model_version:
  stream_name:

```

## Example of Using Edge App Emulator
```python
    import mellerikatedge.edgeapp as edgeapp

    emulator = edgeapp.Emulator('emulator_config.yaml path')
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