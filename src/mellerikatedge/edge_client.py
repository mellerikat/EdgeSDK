import os
import requests
import mellerikatedge.edge_utils as edge_utils

from mellerikatedge.edge_config import EdgeConfig

import json
import asyncio
import nest_asyncio
import websockets

import threading

from datetime import datetime, timezone

from loguru import logger

from mellerikatedge.version import __version__

class EdgeClient:
    url = None
    websocket_url = None
    jwt_token = None
    websocket = None

    def __init__(self, edge_app, config):
        self.edge_app = edge_app
        nest_asyncio.apply()

        self.url = edge_utils.remove_trailing_slash(config.get_config(EdgeConfig.EDGECOND_URL))
        self.security_key = config.get_config(EdgeConfig.SECURITY_KEY)
        if config.get_config(EdgeConfig.EDGECOND_LOCATION) == EdgeConfig.EDGECOND_LOCATION_CLOUD:
            self.websocket_url = f"wss://{edge_utils.remove_http_https(self.url)}/app/api/v1/socket/{self.security_key}"
        else:
            self.websocket_url = f"ws://{edge_utils.remove_http_https(self.url)}/app/api/v1/socket/{self.security_key}"

        self.websocket = None
        self.loop = asyncio.new_event_loop()
        self.thread = None
        self._stop_event = asyncio.Event()
        logger.info(f"WebSocket URL: {self.websocket_url}")


    async def connect_edgeconductor(self):
        headers = {"Authorization": f"Bearer {self.jwt_token}"}
        while not self._stop_event.is_set():
            try:
                self.websocket = await websockets.connect(self.websocket_url, extra_headers=headers)
                logger.info('WebSocket connected')
                asyncio.create_task(self._receive_messages())
                asyncio.create_task(self._keep_alive())
                await self._stop_event.wait()
            except websockets.ConnectionClosed:
                logger.warning("Connection closed, reconnecting in 2 seconds...")
                await asyncio.sleep(2)

    async def _keep_alive(self):
        while not self._stop_event.is_set():
            await asyncio.sleep(5)
            await self.websocket.ping()

    async def _receive_messages(self):
        try:
            while not self._stop_event.is_set():
                message = await self.websocket.recv()
                logger.info(f"Received message: {message}")
                message_dict = json.loads(message)
                if "deploy_model" in message_dict:
                    deploy_model = message_dict["deploy_model"]
                    self.edge_app._receive_deploy_model_message(deploy_model)
                elif "update_edge" in message_dict:
                    edge_state = message_dict["update_edge"]
                    self.edge_app._update_state(edge_state)
                    # "update_edge":{"edge_state":"registered"}
        except websockets.ConnectionClosed:
            logger.info("Connection closed")

    async def close_websocket(self):
        if self.websocket:
            try:
                await self.websocket.close()
                logger.info("WebSocket closed")
            except Exception as e:
                logger.error(f"Failed to close websocket: {e}")
        self.websocket = None

    def run_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self.connect_edgeconductor())
        self.loop.run_until_complete(self.close_websocket())
        self.loop.stop()
        self.loop.close()

    def connect(self):
        if self.websocket is None:
            if self.thread is None or not self.thread.is_alive():
                self.thread = threading.Thread(target=self.run_loop, daemon=True)
                self.thread.start()
                logger.info("WebSocket thread started")
        else:
            logger.debug("Already connected")

    def disconnect(self):
        if self.loop.is_running():
            self.loop.call_soon_threadsafe(self._stop_event.set)
            self.loop.call_soon_threadsafe(lambda: asyncio.ensure_future(self.close_websocket(), loop=self.loop))

            if self.thread:
                self.thread.join(timeout=5)
                if self.thread.is_alive():
                    logger.warning("WebSocket thread did not terminate gracefully")
            logger.info("WebSocket thread stopped")

    def request_register(self, device_info):
        url = f"{self.url}/app/api/v1/edges"

        data = {
            "edge_id": self.security_key,
            "note": "edge sdk",
            "security_key": self.security_key,
            "device_mac": device_info["device_mac"],
            "device_os": device_info["device_os"],
            "device_cpu": device_info["device_cpu"],
            "device_gpu": device_info["device_gpu"]
        }

        response = requests.post(url, json=data)


        if response.status_code == 201:
            logger.info("Success!")
            logger.info("Response JSON:", response.json())
            return True
        elif response.status_code == 202:
            logger.info("Accepted")
        else:
            logger.info("Failed!")
            logger.info("Status Code:", response.status_code)
            logger.info("Response:", response.text)
        return False

    def check_authenticate(self):
        return self.jwt_token != None

    def authenticate(self):
        url = f"{self.url}/app/api/v1/auth/authenticate"

        headers = {
            "device_up_time": "12345",
            "app_installed_time": "1609459200",
            "app_version": f"{__version__}-sdk",
            "app_up_time": "3600",
            "config_input_path": "/path/to/input",
            "config_output_path": "/path/to/output"
        }

        data = {
            "grant_type": "password",
            "username": self.security_key,
            "password": self.security_key,
            "scope": "",
        }

        response = requests.post(url, headers=headers, data=data)

        if response.status_code == 200:
            token = response.json()["access_token"]
            self.jwt_token = token
            logger.info("JWT Token: ", token)
            return True
        else:
            logger.warning("Failed to authenticate:", response.status_code, response.text)
            return False

    def read_info(self):
        url = f"{self.url}/app/api/v1/edges/me"

        headers = {
            "Authorization": f"Bearer {self.jwt_token}",
            "Content-Type": "application/json"
        }

        response = requests.get(url, headers=headers)
        response.raise_for_status()
        edge_details = response.json()
        if edge_details:
            logger.info("GET Success!")
            logger.info("Edge Details:")
            logger.info(f"Edge ID: {edge_details.get('edge_id')}")
            logger.info(f"Edge Name: {edge_details.get('edge_name', 'N/A')}")
            logger.info(f"Edge Desc: {edge_details.get('edge_desc', 'N/A')}")
            logger.info(f"Edge Location: {edge_details.get('edge_location', 'N/A')}")
            logger.info(f"Edge State: {edge_details.get('edge_state')}")
            logger.info(f"Edge Status: {edge_details.get('edge_status', 'N/A')}")
            logger.info(f"Created At: {edge_details.get('created_at', 'N/A')}")
            logger.info(f"Creator: {edge_details.get('creator', 'N/A')}")

            deployed_info = edge_details.get("deployed_info", {})
            deploy_model = edge_details.get("deploy_model", {})
            update_docker = edge_details.get("update_edge_docker", {})

            logger.info(f"\nDeployed Info: {deployed_info}")
            logger.info(f"Deploy Model: {deploy_model}")
            logger.info(f"Update Edge Docker: {update_docker}")

            return edge_details
        else:
            logger.error("GET Failed!")
            return None

    def download_model(self, model_seq, download_dir):
        url = f"{self.url}/app/api/v1/models/{model_seq}/model-file"

        headers = {
            "Authorization": f"Bearer {self.jwt_token}",
        }

        response = requests.get(url, headers=headers, stream=True)

        if response.status_code == 200:
            content_disposition = response.headers.get('Content-Disposition')
            if content_disposition:
                file_name = content_disposition.split('filename=')[-1].strip().strip("\"'")
            else:
                logger.warning("Content-Disposition header is missing.")
                file_name = f"model.tar.gz"

            file_path = os.path.join(download_dir, 'model.tar.gz')
            with open(file_path, 'wb') as file:
                for chunk in response.iter_content(chunk_size=8192):
                    file.write(chunk)
            logger.info(f"{file_name} downloaded successfully.")
        else:
            logger.error("Failed to download the file:", response.status_code, response.text)

    def download_metadata(self, model_seq, download_dir):
        url = f"{self.url}/app/api/v1/models/{model_seq}/meta-data"
        logger.info(url)

        headers = {
            "Authorization": f"Bearer {self.jwt_token}",
        }

        response = requests.get(url, headers=headers, stream=True)

        if response.status_code == 200:
            metadata = response.json()
            file_path = os.path.join(download_dir, 'meta.json')
            with open(file_path, 'w') as file:
                json.dump(metadata, file, indent=2)
            logger.info(f"meta.json downloaded successfully.")
        else:
            logger.error("Failed to download the file:", response.status_code, response.text)

    def update_deploy_status(self, model_seq, status):
        url = f"{self.url}/app/api/v1/models/{model_seq}/deploy-result"
        logger.info(url)

        current_time = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

        headers = {
            "Authorization": f"Bearer {self.jwt_token}",
        }

        data = {
            "deploy_result": status, # "success" "fail"
            "complete_datetime": current_time
        }

        response = requests.put(url, headers=headers, json=data)
        if response.status_code == 200:
            logger.info("Successfully updated deploy result.")
            return True
        else:
            logger.error("Failed to update deploy result:", response.status_code, response.text)
            return False

    def update_inference_status(self, status):
        url = f"{self.url}/app/api/v1/edges/inference-status"

        headers = {
            "Authorization": f"Bearer {self.jwt_token}",
        }

        data = {
            "inference_status": status  # "-", "nostream", "ready", "inferencing"
        }

        response = requests.put(url, headers=headers, json=data)

        if response.status_code == 200:
            logger.info("Successfully updated inference status.")
            logger.info("Response:", response.json())
            return True
        else:
            logger.error("Failed to update inference status:", response.status_code, response.text)
            return False

    def upload_inference_result(self, result_info, zip_path):
        url = f"{self.url}/app/api/v1/inference/file"
        logger.info(url)

        current_time = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

        headers = {
            "Authorization": f"Bearer {self.jwt_token}",
        }

        data = {
            "stream_name": result_info['stream_name'],
            "model_seq": result_info['model_seq'],
            "result": result_info['result'],
            "score": result_info['score'],
            "input_file": result_info['input_file'],
            "date": current_time,
            "note": result_info['note'],
            "tabular": result_info['tabular'],
            "non-tabular": result_info['non-tabular'],
        }

        logger.debug(data)

        if len(result_info['probability']) != 0:
           data["probability"] = result_info['probability']

        files = {
            "data": (None, json.dumps(data), 'application/json'),
            "file": open(zip_path, "rb")
        }

        response = requests.post(url, headers=headers, files=files)
        files["file"].close()

        if response.status_code == 201:
            logger.info("Successfully upload inference result.")
            return True
        else:
            logger.error("Failed to upload inference result:", response.status_code, response.text)
            return False

