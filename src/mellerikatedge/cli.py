import os
import argparse
import re

from mellerikatedge.edge_app import Emulator
import mellerikatedge.edge_utils as edge_utils

CONFIG_FILE_NAME = 'edge_config.yaml'

def edge_inference(input_file):
    if not os.path.isfile(input_file):
        print(f"Error: The file '{input_file}' does not exist.")
        return

    if not os.path.exists(CONFIG_FILE_NAME):
        print(f"Error: The file '{CONFIG_FILE_NAME}' does not exist. Do the 'edge init' first.")
        return

    emulator = Emulator(CONFIG_FILE_NAME)
    emulator.start(onetime_run=True)
    if emulator.deploy_model():
        if emulator.inference_file(input_file):
            emulator.upload_inference_result()
        else:
            print("inference fail")
    else:
        print(f"Performing edge inference on input file: {input_file}")


def edge_init(args):
    current_directory = os.getcwd()
    print(current_directory)

    alo_version = None
    experiments_yaml_path = os.path.join(current_directory, 'experimental_plan.yaml')
    settings_folder_path = os.path.join(current_directory, 'setting')
    infra_config_path = os.path.join(settings_folder_path, 'infra_config.yaml')
    solution_config_path = os.path.join(settings_folder_path, 'solution_info.yaml')

    if os.path.isfile(experiments_yaml_path) and os.path.isdir(settings_folder_path):
        if os.path.isfile(infra_config_path) and os.path.isfile(solution_config_path):
            alo_version = "v3"

    if alo_version is None:
        main_py_path = os.path.join(current_directory, 'main.py')
        register_notebook_path = os.path.join(current_directory, 'register-ai-solution.ipynb')

        if os.path.isfile(main_py_path) and os.path.isfile(register_notebook_path):
            with open(main_py_path, 'r') as file:
                content = file.read()
                if "from src.alo import ALO" in content:
                    alo_version = "v2"

    if alo_version is None:
        print("Please run init in the folder where ALO is executed.")
        return

    def validate_input(prompt, pattern, error_message):
        while True:
            user_input = input(prompt)
            if re.match(pattern, user_input):
                return user_input
            else:
                print(error_message)

    edge_serial_name = validate_input(
        "Enter Edge Serial Name (alphanumeric and dashes only): ",
        r'^[a-zA-Z0-9\-]+$',
        "Edge Serial Name must contain only alphanumeric characters and dashes."
    )

    # Edge Conductor 주소 입력 받기 (http 또는 https로 시작)
    edge_conductor_url = validate_input(
        "Enter Edge Conductor Address (e.g., https://edgecond.try-mellerikat.com): ",
        r'^(http|https)://[^\s]+$',
        "Edge Conductor Address must be a valid URL starting with http or https."
    )

    # Edge Conductor 설치 위치 입력 받기 (1 또는 2만 허용)
    edge_conductor_location = validate_input(
        "Enter Edge Conductor Installation Location (1 for Cloud, 2 for On-premise): ",
        r'^[12]$',
        "Installation Location must be 1 (Cloud) or 2 (On-premise)."
    )

    model_info = {
        'model_seq' : None,
        'model_version' : None,
        'stream_name' : None
    }

    # 데이터 저장
    config_data = {
        'solution_dir' : current_directory,
        'alo_version' : alo_version,
        'edge_security_key': edge_serial_name,
        'edge_conductor_url': edge_conductor_url,
        'edge_conductor_location': "cloud" if edge_conductor_location == '1' else "on-premise",
        'model_info' : model_info
    }

    edge_utils.save_yaml(CONFIG_FILE_NAME, config_data)

    print(f"Configuration file {CONFIG_FILE_NAME} created with the following details:")
    print(f"Edge Serial Name: {edge_serial_name}")
    print(f"Edge Conductor URL: {edge_conductor_url}")
    print(f"Edge Conductor Installation Location: {'cloud' if edge_conductor_location == '1' else 'on-premise'}")

    emulator = Emulator(CONFIG_FILE_NAME)
    exist_edge = emulator.start(onetime_run=True)
    if exist_edge:
        print("This Edge is already registered. Change the Serial Name if you want to use a different Edge.")
    else:
        print("Connect to Edge Conductor and make sure to register the Edge.")


def main():
    parser = argparse.ArgumentParser(description="Mellerikat Edge CLI")
    subparsers = parser.add_subparsers(dest="command")

    # inference 서브 커맨드
    parser_inference = subparsers.add_parser("inference", help="Deploy the model from Edge Conductor and perform inference.")
    parser_inference.add_argument('--input', type=str, required=True, help="Input file path for inference")
    parser_inference.set_defaults(func=lambda args: edge_inference(args.input))

    # init 서브 커맨드
    parser_init = subparsers.add_parser("init", help="Initialize edge environment")
    parser_init.set_defaults(func=edge_init)

    args = parser.parse_args()
    if hasattr(args, 'func'):
        args.func(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()