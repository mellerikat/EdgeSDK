# Edge SDK (mellerikatedge)
- Edge Conductor에 EdgeApp Emulator로 연결하고 Inference 모델을 배포 받아서 실행하는 기능을 제공합니다.
- DataFrame 또는 파일을 직접 활용하여 Inference가 가능합니다.

## 환경 설정
### ALO와 AI Solution 설치 및 실행 환경 구성
- ALO 를 설치합니다.(https://mellerikat.com/user_guide/data_scientist_guide/alo/quick_run)
- Edge Conductor에서 Deploy 받을 Stream의 AI 솔루션을 ALO에 설치합니다.
- 간단한 데이터로 ALO를 실행하여 Asset을 다운 받고 Python 모듈들이 설치 되도록 합니다.

### Edge SDK 설치
- dist 폴더 내의 mellerikatedge 파일을 다운받고, 설치합니다.
- wget https://github.com/mellerikat/EdgeSDK/raw/refs/heads/v1.0.0/dist/mellerikatedge-1.0-py3-none-any.whl
- pip install mellerikatedge-1.0-py3-none-any.whl

### Edge SDK를 위한 config 파일을 생성
임의의 경로에 `emulator_config.yaml` 를 다음의 내용으로 생성합니다.

```
alo_dir: /home/user/projects/alo #ALO 경로
edge_conductor_location: cloud # Edge Conductor의 환경 (cloud or on-primise)
edge_conductor_url: https://edgecond.try-mellerikat.com # Edge Conductor 주소 (https or http 까지 포함)
edge_security_key: edge-emulator-{{user_id}}-{{number}} # Edge를 구분하는 고유키로 {{ }}의 내용을 작성하여 설정
model_info: # SDK가 실행되어 모델을 배포 받으면 작성됩니다.
  model_seq:
  model_version:
  stream_name:

```

## Edge App Emulator Example
```
    from mellerikatedge.edge_app_emulator import EdgeAppEmulator

    emulator = EdgeAppEmulator('emulator_config.yaml path')
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