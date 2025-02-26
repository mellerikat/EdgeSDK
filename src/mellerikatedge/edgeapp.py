import os
import mellerikatedge.edge_utils as edge_utils

import tarfile
import shutil
from mellerikatedge.edge_client import EdgeClient

import pandas as pd

import sys
import importlib
from loguru import logger

#CONFIG

class Emulator:
    jwt_token = None
    CONFIG_MODEL_INFO = {}
    new_model_deployed = False
    initialized = False

    def __init__(self, config_path):
        self.config_path = config_path
        self.config = edge_utils.load_yaml(config_path)

        config_dir = os.path.dirname(config_path)
        self.log_path = os.path.join(config_dir, 'edge.log')

        # logger.remove()
        logger.add(self.log_path, format="{time:YYYY-MM-DD HH:mm:ss}|{level}|{file}:{line}|{message}")

        self.alo_version = self.config[edge_utils.CONFIG_ALO_VERSION]
        logger.info(f"ALO Version : {self.alo_version}")

        self.alo_dir = self.config[edge_utils.CONFIG_SOLUTION_DIR]
        if self.alo_version == "v2":
            self.solution_dir = os.path.join(self.alo_dir, "solution")
            self.train_artifacts_path = os.path.join(self.alo_dir, 'train_artifacts')
            self.update_model_dir = os.path.join(self.train_artifacts_path, 'models')
        else:
            self.solution_dir = self.alo_dir
            self.train_artifacts_path = os.path.join(self.alo_dir, 'train_artifact')
            self.update_model_dir = self.train_artifacts_path

        self.sdk_dir = os.path.join(self.solution_dir, "edge_sdk")
        self.new_model_dir = os.path.join(self.sdk_dir, "model")
        self.inference_data_dir = os.path.join(self.sdk_dir, "inference")

        self.client = EdgeClient(self.config)



    def start(self):
        self.initialized = False

        # edge_utils.self.CONFIG_SOLUTION_DIR = os.path.join(self.alo_dir, "solution")

        if not os.path.exists(self.alo_dir):
            logger.error(f"ALO {self.alo_dir} does not exist.")
            return

        if not os.path.exists(self.alo_dir):
            logger.error(f"ALO {self.alo_dir} does not exist.")
            return

        if not os.path.exists(self.solution_dir):
            logger.error(f"AI Solution {self.solution_dir} does not exist.")
            return

        if not os.path.exists(self.sdk_dir):
            os.makedirs(self.sdk_dir)

        if not os.path.exists(self.new_model_dir):
            os.makedirs(self.new_model_dir)

        if not os.path.exists(self.inference_data_dir):
            os.makedirs(self.inference_data_dir)

        if self.client.authenticate():
            self.client.connect()

            deployed_info, deploy_model = self.client.read_info()

            if deployed_info is None and deploy_model is None:
                logger.error("First, deploy the model on Edge Conductor.")
                return

            if deployed_info is not None and 'model_seq' not in self.config.get(edge_utils.CONFIG_MODEL_INFO, {}):
                logger.error("The model information is incorrect. Deploy the model again")
                return

            if deployed_info is not None and deployed_info['model_seq'] != self.config[edge_utils.CONFIG_MODEL_INFO]['model_seq']:
                logger.error("The model information is incorrect. Please delete the information in the configuration.")
                return

            if deploy_model != None:
                logger.info("New model deployed")
                self.CONFIG_MODEL_INFO['model_seq'] = deploy_model['model_seq']
                self.CONFIG_MODEL_INFO['model_version'] = deploy_model['model_version']
                self.CONFIG_MODEL_INFO['stream_name'] = deploy_model['stream_name']
                self.new_model_deployed = True
            else :
                self.CONFIG_MODEL_INFO = {}
                self.new_model_deployed = False


            self.initialized = True
        else:
            device_info = edge_utils.get_device_info()
            logger.info(device_info)
            self.client.request_register(device_info)

    def stop(self):
        self.client.disconnect()

    def deploy_model(self):
        if self.initialized is not True:
            logger.warning('Not initialized')
            return False

        if self.new_model_deployed is not True:
            logger.info('Use exist model')
            return True
        else:
            logger.info("Deploy new model")

            self.client.download_model(self.CONFIG_MODEL_INFO['model_seq'], self.new_model_dir)
            self.client.download_metadata(self.CONFIG_MODEL_INFO['model_seq'], self.new_model_dir)

            # Model
            model_file_name = "model.tar.gz"
            model_zip_path = os.path.join(self.new_model_dir, model_file_name)
            if not os.path.exists(model_zip_path):
                logger.error(f"File {model_zip_path} does not exist.")
                initialized = False
                return

            # Create Model Dir
            if os.path.exists(self.train_artifacts_path):
                shutil.rmtree(self.train_artifacts_path)
            os.makedirs(self.update_model_dir)

            # if self.alo_version == "v2":
            #     model_path = os.path.join(self.train_artifacts_path, 'models')
            #     os.makedirs(model_path)

            if self.alo_version == "v2":
                try:
                    with tarfile.open(model_zip_path, "r:gz") as tar:
                        tar.extractall(path=self.update_model_dir)
                        logger.info(f"Extracted {model_zip_path} to {self.update_model_dir} successfully.")

                    self.config[edge_utils.CONFIG_MODEL_INFO] = self.CONFIG_MODEL_INFO

                except tarfile.TarError as e:
                    logger.error(f"An error occurred: {e}")
                    initialized = False
                    return False
            else:
                try:
                    edge_utils.copy_file_to_folder(model_zip_path, self.update_model_dir)
                except Exception as e:
                    logger.error(f"Update model error: {e}")

            #Metadata
            try:
                meta_file_name = "meta.json"
                metadata_path = os.path.join(self.new_model_dir, meta_file_name)

                if not os.path.exists(metadata_path):
                    logger.error(f"File {metadata_path} does not exist.")
                    initialized = False
                    return False

                if self.alo_version == "v2":
                    metadata_json = edge_utils.load_json(metadata_path)
                    logger.info("extract user parameter")
                    selected_train_parameter, selected_inference_parameter = edge_utils.extract_selected_user_parameters(metadata_json)

                    plan_path = os.path.join(self.solution_dir, 'experimental_plan.yaml')
                    plan_yaml = edge_utils.load_yaml(plan_path)
                    # logger.info("update train parameter")
                    # train_pipeline = plan_yaml['user_parameters'][0]['train_pipeline']
                    # updated_train_pipeline = edge_utils.update_pipeline(train_pipeline, selected_train_parameter)
                    # plan_yaml['user_parameters'][0]['train_pipeline'] = updated_train_pipeline

                    logger.info("update inference parameter")
                    inference_pipeline = plan_yaml['user_parameters'][1]['inference_pipeline']
                    print(inference_pipeline)
                    print(selected_inference_parameter)
                    updated_inference_pipeline = edge_utils.update_pipeline(inference_pipeline, selected_inference_parameter)
                    plan_yaml['user_parameters'][1]['inference_pipeline'] = updated_inference_pipeline

                    logger.info("save plan yaml")
                    edge_utils.save_yaml(plan_path, plan_yaml)
            except Exception as e:
                logger.error(f"Update metadata error: {e}")
                logger.error("Please confirm if the version of AI Solution code is the same.")
                initialized = False
                return False

            if self.client.update_deploy_status(self.CONFIG_MODEL_INFO['model_seq'], "success"):
                logger.info("update_deploy_status Success")
                edge_utils.save_yaml(self.config_path, self.config)
                return True
            else:
                logger.error("update_deploy_status fail")
                self.initialized = False
                return False


    def inference_file(self, file_path):
        logger.info(f"inference_file : {file_path}")
        if self.initialized is not True:
            logger.warning('Not initialized')
            return

        plan_path = os.path.join(self.solution_dir, "experimental_plan.yaml")

        if os.path.exists(self.inference_data_dir):
            shutil.rmtree(self.inference_data_dir)
        os.makedirs(self.inference_data_dir)

        edge_utils.copy_file_to_folder(file_path, self.inference_data_dir)

        plan_yaml = edge_utils.load_yaml(plan_path)
        edge_utils.update_inference_data_path(plan_yaml, self.inference_data_dir)
        edge_utils.save_yaml(plan_path, plan_yaml)

        return self.run_alo_inference()

    def inference_dataframe(self, df: pd.DataFrame):
        logger.info(f"inference_dataframe : df length {len(df)}")
        if self.initialized is not True:
            logger.warning('Not initialized')
            return

        self.alo_dir = self.config[edge_utils.self.CONFIG_SOLUTION_DIR]
        if self.CONFIG_ALO_VERSION == "v2":
            self.CONFIG_SOLUTION_DIR = os.path.join(self.alo_dir, "solution")
        else :
            self.CONFIG_SOLUTION_DIR = self.alo_dir

        plan_path = os.path.join(self.CONFIG_SOLUTION_DIR, "experimental_plan.yaml")
        inference_data_dir = os.path.join(self.CONFIG_SOLUTION_DIR, "emulator_inference")
        inference_data_path = os.path.join(inference_data_dir, "inference_input.csv")

        if os.path.exists(inference_data_dir):
            shutil.rmtree(inference_data_dir)
        os.makedirs(inference_data_dir)

        df.to_csv(inference_data_path, index=False)

        plan_yaml = edge_utils.load_yaml(plan_path)
        edge_utils.update_inference_data_path(plan_yaml, inference_data_dir)
        edge_utils.save_yaml(plan_path, plan_yaml)

        return self.run_alo_inference()

    def run_alo_inference(self):
        if self.initialized is not True:
            logger.warning('Not initialized')
            return

        logger.info('run_alo_inference')

        self.alo_dir = self.config[edge_utils.self.CONFIG_SOLUTION_DIR]

        sdk_working_dir = os.getcwd()
        success = True
        try:
            os.chdir(self.alo_dir)
            sys.path.append(self.alo_dir)
            # src_utils = importlib.import_module('src.utils')
            # set_args = src_utils.set_args
            # kwargs = vars(set_args())
            # kwargs['mode'] = 'inference'

            kwargs = {'config': None, 'system': None, 'mode': 'inference', 'loop': False, 'computing': 'local'}

            src_alo = importlib.import_module('src.alo')
            ALO = src_alo.ALO
            alo_instance = ALO(**kwargs)
            alo_instance.main()

        except:
            logger.error('run alo fail')
            success = False
        finally:
            os.chdir(sdk_working_dir)

        return success

    def upload_inference_result(self):
        if self.initialized is not True:
            logger.warning('Not initialized')
            return

        logger.info('upload_inference_result')

        self.alo_dir = self.config[edge_utils.self.CONFIG_SOLUTION_DIR]

        inference_artifacts_folder = os.path.join(self.alo_dir, 'inference_artifacts')
        output_folder = os.path.join(inference_artifacts_folder, 'output')
        score_folder = os.path.join(inference_artifacts_folder, 'score')
        score_path = os.path.join(score_folder, 'inference_summary.yaml')

        if not os.path.exists(output_folder):
            logger.error('output folder is not exist')
            return

        score_yaml = edge_utils.load_yaml(score_path)
        logger.info(score_yaml['note'])

        zip_path = os.path.join(self.alo_dir, 'inference_artifacts.zip')

        edge_utils.zip_folder(inference_artifacts_folder, zip_path)

        CONFIG_MODEL_INFO = self.config[edge_utils.CONFIG_MODEL_INFO]
        result_info = CONFIG_MODEL_INFO
        result_info['result'] = score_yaml['result']
        result_info['score'] = score_yaml['score']
        result_info['note'] = score_yaml['note']

        tabular_path = edge_utils.find_tabular_file(output_folder)
        if tabular_path is not None:
            result_info['tabular'] = f"output/{tabular_path}"
        else:
            result_info['tabular'] = None

        image_path = edge_utils.find_image_file(output_folder)
        if image_path is not None:
            result_info['non-tabular'] = f"output/{image_path}"
        else :
            result_info['non-tabular'] = None

        result_info["probability"] = {}

        if len(score_yaml['probability']) != 0:
           result_info["probability"] = score_yaml['probability']

        self.client.upload_inference_result(result_info, zip_path)

if __name__ == '__main__' :
    # emulator = EdgeAppEmulator('/home/gyulim.gu/projects/edge_sdk/test/emulator_config.yaml')

    # try :
    #     emulator.start()
    #     emulator.deploy_model()
    #     if emulator.inference_file("/home/gyulim.gu/projects/edge_sdk/test/20240903-134104.945.csv"):
    #         emulator.upload_inference_result()
    # finally:
    #     emulator.stop()

    emulator = EdgeAppEmulator('/home/gyulim.gu/projects/edge_sdk/test/emulator_config_tcr.yaml')

    try :
        emulator.start()
        if emulator.deploy_model():
            if emulator.inference_file("/home/gyulim.gu/projects/edge_sdk/test/test_data.csv"):
                emulator.upload_inference_result()
    finally:
        emulator.stop()
