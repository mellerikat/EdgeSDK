import os
import mellerikatedge.edge_utils as edge_utils

import tarfile
import shutil
from mellerikatedge.edge_client import EdgeClient
from mellerikatedge.edge_config import EdgeConfig
import pandas as pd

import sys
import importlib
from loguru import logger

import subprocess

class Emulator:
    STATUS_INIT = "init"
    STATUS_REQUEST_REGISTER = "register"
    STATUS_NO_STREAM = "no_stream"
    STATUS_INFERENCE_READY = "inference"
    STATUS_ERROR = "error"

    status = STATUS_ERROR

    def __init__(self, config_path):
        self.edge_config = EdgeConfig()
        self.edge_config.load_config(config_path)

        config_dir = os.path.dirname(config_path)
        self.log_path = os.path.join(config_dir, 'edge.log')

        # logger.remove()
        logger.add(self.log_path, format="{time:YYYY-MM-DD HH:mm:ss}|{level}|{file}:{line}|{message}")

        self.alo_version = self.edge_config.get_config(EdgeConfig.ALO_VERSION)
        logger.info(f"ALO Version : {self.alo_version}")

        self.alo_dir = self.edge_config.get_config(EdgeConfig.SOLUTION_DIR)
        if self.alo_version == "v2":
            self.solution_dir = os.path.join(self.alo_dir, "solution")
            self.train_artifact_dir = os.path.join(self.alo_dir, 'train_artifacts')
            self.inference_artifact_dir = os.path.join(self.alo_dir, 'inference_artifacts')
            self.update_model_dir = os.path.join(self.train_artifact_dir, 'models')
        else:
            self.solution_dir = self.alo_dir
            self.train_artifact_dir = os.path.join(self.alo_dir, 'train_artifact')
            self.inference_artifact_dir = os.path.join(self.alo_dir, 'inference_artifact')
            self.update_model_dir = self.train_artifact_dir

        self.edge_dir = os.path.join(self.solution_dir, "mellerikat_edge")
        self.new_model_dir = os.path.join(self.edge_dir, "model")
        self.inference_data_dir = os.path.join(self.edge_dir, "inference")

        self.plan_path = os.path.join(self.solution_dir, "experimental_plan.yaml")

        self.model_updated = False

        self.train_parameter = None
        self.inference_parameter = None

        self.deployed_model_info = None

        if not os.path.exists(self.alo_dir):
            logger.error(f"ALO {self.alo_dir} does not exist.")
            self.status = self.STATUS_ERROR

        if not os.path.exists(self.alo_dir):
            logger.error(f"ALO {self.alo_dir} does not exist.")
            self.status = self.STATUS_ERROR

        if not os.path.exists(self.solution_dir):
            logger.error(f"AI Solution {self.solution_dir} does not exist.")
            self.status = self.STATUS_ERROR

        if not os.path.exists(self.edge_dir):
            os.makedirs(self.edge_dir)

        if not os.path.exists(self.new_model_dir):
            os.makedirs(self.new_model_dir)

        if not os.path.exists(self.inference_data_dir):
            os.makedirs(self.inference_data_dir)

        if self.status != self.STATUS_ERROR:
            self.status = self.STATUS_INIT

        self.client = EdgeClient(self, self.edge_config)

    def register(self):
        if not self.client.check_authenticate():
            if not self.client.authenticate():
                device_info = edge_utils.get_device_info()
                if self.client.request_register(device_info):
                    logger.info(f"Registration requested for {self.edge_config.get_config(EdgeConfig.SECURITY_KEY)}.")
                    self.status = self.STATUS_REQUEST_REGISTER
                else:
                    logger.error("Request registration Error")
                    self.status = self.STATUS_ERROR
                    return self.status

        if self.status == self.STATUS_ERROR:
            self.status = self.STATUS_REQUEST_REGISTER
        return self.status

    def _update_state(self, edge_state):
        logger.info(f"Update State : {edge_state}")
        if edge_state['edge_state'] == "registered":
            self.status = self.STATUS_NO_STREAM

    def start(self, onetime_run=False):
        if not self.client.check_authenticate():
            if not self.client.authenticate():
                logger.warning("Execute init first.")
                self.status = self.STATUS_ERROR
                return self.status

        if self.status == self.STATUS_ERROR:
            logger.error('The environment is not one in which the "mellerikat edge" can operate.')
            return self.status

        if onetime_run == False:
            self.client.connect()

        if self.deployed_model_info is None:
            new_model_info = None

            edge_details = self.client.read_info()
            deployed_info = edge_details.get("deployed_info", {})
            deploy_info = edge_details.get("deploy_model", {})

            if edge_details.get('edge_state') == 'requested':
                logger.error("Register the Edge App on Edge Conductor.")
                self.status = self.STATUS_REQUEST_REGISTER
                return self.status

            if deployed_info is None and deploy_info is None:
                logger.error("The model must be deployed from Edge Conductor.")
                self.status = self.STATUS_NO_STREAM
                return self.status

            if deploy_info != None:
                logger.info("Deploy new model")
                new_model_info = deploy_info
            elif deployed_info is not None:
                if self.edge_config.get_config(EdgeConfig.MODEL_INFO)['model_seq'] != deployed_info['model_seq']:
                    logger.warning("Redeploying because the existing model information differs from EdgeConductor.")
                    new_model_info = deployed_info
                else:
                    self.deployed_model_info = deployed_info
                    self.status = self.STATUS_INFERENCE_READY

            if new_model_info is not None:
                self._deploy_model(new_model_info)

        return self.status

    def stop(self):
        self.client.disconnect()

    def get_status(self):
        return self.status

    def get_deployed_model_info(self):
        if self.deployed_model_info is None:
            return None
        return self.deployed_model_info.copy()

    def get_inference_parameter(self):
        if self.inference_parameter is None:
            return None
        return self.inference_parameter.copy()

    def get_train_parameter(self):
        if self.train_parameter is None:
            return None
        return self.train_parameter.copy()

    def _receive_deploy_model_message(self, new_model_info):
        logger.info('Receive deploy model message')
        self._deploy_model(new_model_info)

    def _deploy_model(self, new_model_info):
        logger.info(f"Deploy new model info : {new_model_info}")
        self.status = self.STATUS_NO_STREAM
        self.deployed_model_info = None

        self.client.download_model(new_model_info['model_seq'], self.new_model_dir)
        self.client.download_metadata(new_model_info['model_seq'], self.new_model_dir)

        # Model
        model_file_name = "model.tar.gz"
        model_zip_path = os.path.join(self.new_model_dir, model_file_name)
        if not os.path.exists(model_zip_path):
            logger.error(f"File {model_zip_path} does not exist.")
            return

        # Create Model Dir
        if not os.path.exists(self.update_model_dir):
            os.makedirs(self.update_model_dir)
        else:
            logger.warning("Overwriting the existing model file.")

        if self.alo_version == "v2":
            try:
                with tarfile.open(model_zip_path, "r:gz") as tar:
                    tar.extractall(path=self.update_model_dir)
                    logger.info(f"Extracted {model_zip_path} to {self.update_model_dir} successfully.")
            except tarfile.TarError as e:
                logger.error(f"An error occurred: {e}")
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

            metadata_json = edge_utils.load_json(metadata_path)
            logger.info("extract user parameter")
            selected_train_parameter, selected_inference_parameter = edge_utils.extract_selected_user_parameters(metadata_json)

            plan_path = os.path.join(self.solution_dir, 'experimental_plan.yaml')
            plan_yaml = edge_utils.load_yaml(plan_path)

            logger.info("update inference parameter")
            if self.alo_version == "v2":
                inference_pipeline = plan_yaml['user_parameters'][1]['inference_pipeline']
                print(inference_pipeline)
                print(selected_inference_parameter)
                updated_inference_pipeline = edge_utils.update_pipeline_v2(inference_pipeline, selected_inference_parameter)
                plan_yaml['user_parameters'][1]['inference_pipeline'] = updated_inference_pipeline
                edge_utils.save_yaml(plan_path, plan_yaml)
            else:
                logger.info("meta v3")
                logger.info(f"{selected_inference_parameter}")
                plan_yaml['solution']['function'] = edge_utils.update_pipeline_v3(plan_yaml['solution']['function'], selected_inference_parameter)
                logger.info(f"{plan_yaml['solution']['function']}")
                edge_utils.save_yaml(plan_path, plan_yaml)

            self.inference_parameter = selected_inference_parameter
            self.train_parameter = selected_train_parameter

        except Exception as e:
            logger.error(f"Update metadata error: {e}")
            logger.error("Please confirm if the version of AI Solution code is the same.")

        if self.client.update_deploy_status(new_model_info['model_seq'], "success"):
            logger.info("update_deploy_status Success")

            self.edge_config.set_config(EdgeConfig.MODEL_INFO, new_model_info)
            self.edge_config.save_config()

            self.deployed_model_info = new_model_info
            self.status = self.STATUS_INFERENCE_READY
        else:
            logger.error("update_deploy_status fail")


    def inference_file(self, file_path):
        logger.info(f"inference_file : {file_path}")
        if self.status != self.STATUS_INFERENCE_READY:
            logger.warning('The model has not been deployed.')
            return

        if os.path.exists(self.inference_data_dir):
            shutil.rmtree(self.inference_data_dir)
        os.makedirs(self.inference_data_dir)

        edge_utils.copy_file_to_folder(file_path, self.inference_data_dir)

        plan_yaml = edge_utils.load_yaml(self.plan_path)
        edge_utils.update_inference_data_path(self.alo_version, plan_yaml, self.inference_data_dir)
        edge_utils.save_yaml(self.plan_path, plan_yaml)

        self.input_name = os.path.basename(file_path)

        return self.run_alo_inference()

    def inference_dataframe(self, df: pd.DataFrame):
        logger.info(f"inference_dataframe : df length {len(df)}")
        if self.status != self.STATUS_INFERENCE_READY:
            logger.warning('The model has not been deployed.')
            return

        inference_data_path = os.path.join(self.inference_data_dir, "dataframe.csv")

        if os.path.exists(self.inference_data_dir):
            shutil.rmtree(self.inference_data_dir)
        os.makedirs(self.inference_data_dir)

        df.to_csv(inference_data_path, index=False)

        plan_yaml = edge_utils.load_yaml(self.plan_path)
        edge_utils.update_inference_data_path(self.alo_version, plan_yaml, self.inference_data_dir)
        edge_utils.save_yaml(self.plan_path, plan_yaml)

        self.input_name = "dataframe.csv"

        return self.run_alo_inference()

    def run_alo_inference(self):
        if self.status != self.STATUS_INFERENCE_READY:
            logger.warning('The model has not been deployed.')
            return

        logger.info('run_alo_inference')
        success = True
        if self.alo_version == "v2":
            sdk_working_dir = os.getcwd()
            try:
                os.chdir(self.alo_dir)
                sys.path.append(self.alo_dir)

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
        else:
            command = ["alo", "run", "--mode", "inference"]
            result = subprocess.run(command, cwd=self.solution_dir)
            logger.info(f"Return code: {result.returncode}")
            if result.stdout:
                logger.info(f"Output: {result.stdout.decode()}")
            if result.stderr:
                success = False
                logger.Error(f"Error: {result.stderr.decode()}")

        return success

    def upload_existing_result(self, input_name):
        self.input_name = input_name
        self.upload_inference_result()

    def upload_inference_result(self):
        if self.status != self.STATUS_INFERENCE_READY:
            logger.warning('The model has not been deployed.')
            return

        logger.info('upload_inference_result')

        if self.alo_version == "v2":
            output_folder = os.path.join(self.inference_artifact_dir, 'output')
            score_folder = os.path.join(self.inference_artifact_dir, 'score')
            score_path = os.path.join(score_folder, 'inference_summary.yaml')

            if not os.path.exists(output_folder):
                logger.error('output folder is not exist')
                return

            score_yaml = edge_utils.load_yaml(score_path)
            logger.info(score_yaml['note'])

            zip_path = os.path.join(self.alo_dir, 'inference_artifacts.zip')

            edge_utils.zip_folder(self.inference_artifact_dir, zip_path)
            tabular_path = edge_utils.find_tabular_file(output_folder)
            if tabular_path is not None:
                tabular_path = f"output/{tabular_path}"

            image_path = edge_utils.find_image_file(output_folder)
            if image_path is not None:
                tabular_path = f"output/{image_path}"
        else:
            zip_path = os.path.join(self.inference_artifact_dir, 'inference_artifacts.zip')
            image_path, tabular_path, score_yaml = edge_utils.parse_inference_artifacts(zip_path)

        logger.info(f"Image Path:{image_path}, Tabular Path:{tabular_path}, Score:{score_yaml}")

        model_info = self.deployed_model_info
        result_info = {}
        result_info['model_seq'] = model_info['model_seq']
        result_info['stream_name'] = model_info['stream_name']
        result_info['result'] = score_yaml['result']
        result_info['score'] = score_yaml['score']
        result_info['note'] = score_yaml['note']
        result_info['input_file'] = self.input_name

        if tabular_path is not None:
            result_info['tabular'] = tabular_path
        else:
            result_info['tabular'] = None

        if image_path is not None:
            result_info['non-tabular'] = image_path
        else :
            result_info['non-tabular'] = None

        result_info["probability"] = {}

        if len(score_yaml['probability']) != 0:
           result_info["probability"] = score_yaml['probability']

        logger.info(result_info)

        if result_info['result'] is None or result_info['score'] is None or (result_info['tabular'] is None and result_info['non-tabular'] is None):
            logger.error("There are no inference results to upload.")
            return False
        else:
            return self.client.upload_inference_result(result_info, zip_path)