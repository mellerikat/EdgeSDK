import os
import platform
import uuid
import psutil
import json
# import yaml
import glob
import zipfile
import shutil
from loguru import logger

from ruamel.yaml import YAML
yaml = YAML()
yaml.preserve_quotes = True  # 따옴표 스타일 유지 (선택)
yaml.indent(mapping=2, sequence=4, offset=2)  # 들여쓰기 설정 (선택)

# config
CONFIG_SOLUTION_DIR = "solution_dir"
CONFIG_ALO_VERSION = "alo_version"
CONFIG_EDGE_COND_URL = "edge_conductor_url"

CONFIG_EDGE_COND_LOCATION = "edge_conductor_location"
CONFIG_EDGE_COND_LOCATION_CLOUD = "cloud"
CONFIG_EDGE_COND_LOCATION_ONPREMISE = "onprimise"

CONFIG_EDGE_SECURITY_KEY = "edge_security_key"
CONFIG_MODEL_INFO = "model_info"

def zip_folder(folder_path, output_path):
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, start=folder_path)
                zipf.write(file_path, arcname)


def load_yaml(path):
    # with open(path, 'r') as file:
    #     yaml_data = yaml.safe_load(file)
    with open(path, 'r') as file:
        yaml_data = yaml.load(file)
    return yaml_data

def save_yaml(path, yaml_data):
    with open(path, 'w') as file:
        # yaml.dump(yaml_data, file, default_flow_style=False)
        yaml.dump(yaml_data, file)

def load_json(file_path):
    with open(file_path, "r") as file:
        data = json.load(file)
    return data


def get_device_info():
    os_info = platform.system() + " " + platform.release()
    mac_address = ":".join(
        [
            "{:02x}".format((uuid.getnode() >> elements) & 0xFF)
            for elements in range(0, 2 * 6, 2)
        ][::-1]
    )
    cpu_info = platform.processor()

    # Extract additional CPU details using psutil
    cpu_count_logical = psutil.cpu_count(logical=True)
    cpu_count_physical = psutil.cpu_count(logical=False)
    cpu_usage = psutil.cpu_percent(interval=1)
    cpu_frequency = psutil.cpu_freq().current if psutil.cpu_freq() else "N/A"

    gpu_info = "N/A"

    return {
        "device_mac": mac_address,
        "device_os": os_info,
        "device_cpu": f"{cpu_info} (Logical: {cpu_count_logical}, Physical: {cpu_count_physical}, Usage: {cpu_usage}%, Frequency: {cpu_frequency} MHz)",
        "device_gpu": gpu_info,
    }


def find_image_file(directory):
    image_extensions = [".png", ".jpg", ".jpeg", ".gif", ".bmp"]
    image_files = []

    for extension in image_extensions:
        image_files.extend(glob.glob(os.path.join(directory, f"*{extension}")))

    if len(image_files) == 0:
        return None
    elif len(image_files) == 1:
        return os.path.basename(image_files[0])
    else:
        logger.warning("There are multiple result files.")
        return os.path.basename(image_files[0])


def find_tabular_file(directory):
    tabualr_extensions = [".csv"]
    tabular_files = []

    for extension in tabualr_extensions:
        tabular_files.extend(glob.glob(os.path.join(directory, f"*{extension}")))

    if len(tabular_files) == 0:
        return None
    elif len(tabular_files) == 1:
        return os.path.basename(tabular_files[0])
    else:
        logger.warning("There are multiple result files.")
        return os.path.basename(tabular_files[0])


def remove_http_https(url):
    if url.startswith("http://"):
        return url[len("http://") :]
    elif url.startswith("https://"):
        return url[len("https://") :]
    return url


def remove_trailing_slash(url):
    return url.rstrip("/")


def copy_file_to_folder(source_file, destination_folder):
    if not os.path.exists(destination_folder):
        os.makedirs(destination_folder)

    file_name = os.path.basename(source_file)
    destination_file = os.path.join(destination_folder, file_name)
    shutil.copy2(source_file, destination_file)


# def update_load_inference_data_path(file_path, new_path):
#     # 파일 읽기
#     with open(file_path, 'r') as file:
#         lines = file.readlines()

#     # 파일 내용 수정
#     for i, line in enumerate(lines):
#         if line.lstrip().startswith("- load_inference_data_path:"):
#             indentation = line[:line.index('-')]
#             lines[i] = f"{indentation}- load_inference_data_path: {new_path}\n"
#             break

#     # 수정된 내용을 파일에 다시 쓰기
#     with open(file_path, 'w') as file:
#         file.writelines(lines)


def update_train_data_path(data, new_path):
    for item in data["external_path"]:
        if "load_train_data_path" in item:
            item["load_train_data_path"] = new_path
    return data


def update_inference_data_path(alo_version, data, new_path):
    if alo_version == "v2":
        for item in data["external_path"]:
            if "load_inference_data_path" in item:
                item["load_inference_data_path"] = new_path
    else:
        data["solution"]["inference"]["dataset_uri"] = new_path

    return data


def extract_selected_user_parameters(data):
    train_selected_user_parameters = None
    inference_selected_user_parameters = None

    for item in data["pipeline"]:
        if item["type"] == "train":
            train_selected_user_parameters = item["parameters"][
                "selected_user_parameters"
            ]
        elif item["type"] == "inference":
            inference_selected_user_parameters = item["parameters"][
                "selected_user_parameters"
            ]

    return train_selected_user_parameters, inference_selected_user_parameters


def update_pipeline_v2(pipeline, selected_parameters):
    for selected in selected_parameters:
        step_to_find = selected["step"]
        for step in pipeline:
            if step["step"] == step_to_find:
                if step["args"] is None:
                    step["args"] = selected["args"]
                else:
                    if selected["args"]:
                        step["args"].update(selected["args"])
    return pipeline


def update_pipeline_v3(pipeline, selected_parameters):
    for parameter in selected_parameters:
        step = parameter['step']
        args = parameter.get('args', {})
        if step in pipeline:
            if 'argument' in pipeline[step]:
                pipeline[step]['argument'].update(args)
            else:
                pipeline[step]['argument'] = args
    return pipeline


def parse_inference_artifacts(path):
    image_path = None
    tabular_path = None
    yaml_data = None
    image_extensions = ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.tif', '.webp')

    with zipfile.ZipFile(path, 'r') as zip_ref:
        for file_info in zip_ref.infolist():
            if file_info.filename.startswith('output/'):
                if file_info.filename.lower().endswith(image_extensions):
                    image_path = file_info.filename
                elif file_info.filename.lower().endswith('.csv'):
                    tabular_path = file_info.filename

            # Check for YAML file in score directory
            if file_info.filename == 'score/inference_summary.yaml':
                with zip_ref.open(file_info) as yaml_file:
                    yaml_data = yaml.load(yaml_file)

            # Exit early if all paths and YAML data are found
            if image_path and tabular_path and yaml_data:
                break

    return image_path, tabular_path, yaml_data