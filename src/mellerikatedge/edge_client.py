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

    def __init__(self, edge_app, config, logger_edge):
        self.edge_app = edge_app
        self.logger_edge = logger_edge
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
        self.logger_edge.info(f"WebSocket URL: {self.websocket_url}")


    async def connect_edgeconductor(self):
        headers = {"Authorization": f"Bearer {self.jwt_token}"}
        while not self._stop_event.is_set():
            try:
                self.websocket = await websockets.connect(self.websocket_url, extra_headers=headers)
                self.logger_edge.info('WebSocket connected')
                asyncio.create_task(self._receive_messages())
                asyncio.create_task(self._keep_alive())
                await self._stop_event.wait()
            except websockets.ConnectionClosed:
                self.logger_edge.warning("Connection closed, reconnecting in 2 seconds...")
                await asyncio.sleep(2)

    async def _keep_alive(self):
        while not self._stop_event.is_set():
            await asyncio.sleep(5)
            await self.websocket.ping()

    async def _receive_messages(self):
        try:
            while not self._stop_event.is_set():
                message = await self.websocket.recv()
                self.logger_edge.info(f"Received message: {message}")
                message_dict = json.loads(message)
                if "deploy_model" in message_dict:
                    deploy_model = message_dict["deploy_model"]
                    self.edge_app._receive_deploy_model_message(deploy_model)
                elif "update_edge" in message_dict:
                    edge_state = message_dict["update_edge"]
                    self.edge_app._update_state(edge_state)
                    # "update_edge":{"edge_state":"registered"}
        except websockets.ConnectionClosed:
            self.logger_edge.info("Connection closed")

    async def close_websocket(self):
        if self.websocket:
            try:
                await self.websocket.close()
                self.logger_edge.info("WebSocket closed")
            except Exception as e:
                self.logger_edge.error(f"Failed to close websocket: {e}")
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
                self.logger_edge.info("WebSocket thread started")
        else:
            self.logger_edge.debug("Already connected")

    def disconnect(self):
        if self.loop.is_running():
            self.loop.call_soon_threadsafe(self._stop_event.set)
            self.loop.call_soon_threadsafe(lambda: asyncio.ensure_future(self.close_websocket(), loop=self.loop))

            if self.thread:
                self.thread.join(timeout=5)
                if self.thread.is_alive():
                    self.logger_edge.warning("WebSocket thread did not terminate gracefully")
            self.logger_edge.info("WebSocket thread stopped")

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
            self.logger_edge.info("Success!")
            self.logger_edge.info("Response JSON:", response.json())
            return True
        elif response.status_code == 202:
            self.logger_edge.info("Accepted")
        else:
            self.logger_edge.info("Failed!")
            self.logger_edge.info("Status Code:", response.status_code)
            self.logger_edge.info("Response:", response.text)
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
            self.logger_edge.info("JWT Token: ", token)
            return True
        else:
            self.logger_edge.warning("Failed to authenticate:", response.status_code, response.text)
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
            self.logger_edge.info("GET Success!")
            self.logger_edge.info("Edge Details:")
            self.logger_edge.info(f"Edge ID: {edge_details.get('edge_id')}")
            self.logger_edge.info(f"Edge Name: {edge_details.get('edge_name', 'N/A')}")
            self.logger_edge.info(f"Edge Desc: {edge_details.get('edge_desc', 'N/A')}")
            self.logger_edge.info(f"Edge Location: {edge_details.get('edge_location', 'N/A')}")
            self.logger_edge.info(f"Edge State: {edge_details.get('edge_state')}")
            self.logger_edge.info(f"Edge Status: {edge_details.get('edge_status', 'N/A')}")
            self.logger_edge.info(f"Created At: {edge_details.get('created_at', 'N/A')}")
            self.logger_edge.info(f"Creator: {edge_details.get('creator', 'N/A')}")

            deployed_info = edge_details.get("deployed_info", {})
            deploy_model = edge_details.get("deploy_model", {})
            update_docker = edge_details.get("update_edge_docker", {})

            self.logger_edge.info(f"\nDeployed Info: {deployed_info}")
            self.logger_edge.info(f"Deploy Model: {deploy_model}")
            self.logger_edge.info(f"Update Edge Docker: {update_docker}")

            return edge_details
        else:
            self.logger_edge.error("GET Failed!")
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
                self.logger_edge.warning("Content-Disposition header is missing.")
                file_name = f"model.tar.gz"

            file_path = os.path.join(download_dir, 'model.tar.gz')
            with open(file_path, 'wb') as file:
                for chunk in response.iter_content(chunk_size=8192):
                    file.write(chunk)
            self.logger_edge.info(f"{file_name} downloaded successfully.")
        else:
            self.logger_edge.error("Failed to download the file:", response.status_code, response.text)

    def download_metadata(self, model_seq, download_dir):
        url = f"{self.url}/app/api/v1/models/{model_seq}/meta-data"
        self.logger_edge.info(url)

        headers = {
            "Authorization": f"Bearer {self.jwt_token}",
        }

        response = requests.get(url, headers=headers, stream=True)

        if response.status_code == 200:
            metadata = response.json()
            file_path = os.path.join(download_dir, 'meta.json')
            with open(file_path, 'w') as file:
                json.dump(metadata, file, indent=2)
            self.logger_edge.info(f"meta.json downloaded successfully.")
        else:
            self.logger_edge.error("Failed to download the file:", response.status_code, response.text)

    def update_deploy_status(self, model_seq, status):
        url = f"{self.url}/app/api/v1/models/{model_seq}/deploy-result"
        self.logger_edge.info(url)

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
            self.logger_edge.info("Successfully updated deploy result.")
            return True
        else:
            self.logger_edge.error("Failed to update deploy result:", response.status_code, response.text)
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
            self.logger_edge.info("Successfully updated inference status.")
            self.logger_edge.info("Response:", response.json())
            return True
        else:
            self.logger_edge.error("Failed to update inference status:", response.status_code, response.text)
            return False

    def upload_inference_result(self, result_info, zip_path):
        url = f"{self.url}/app/api/v1/inference/file"
        self.logger_edge.info(url)

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

        self.logger_edge.debug(data)

        if len(result_info['probability']) != 0:
           data["probability"] = result_info['probability']

        files = {
            "data": (None, json.dumps(data), 'application/json'),
            "file": open(zip_path, "rb")
        }

        response = requests.post(url, headers=headers, files=files)
        files["file"].close()

        if response.status_code == 201:
            self.logger_edge.info("Successfully upload inference result.")
            return True
        else:
            self.logger_edge.error("Failed to upload inference result:", response.status_code, response.text)
            return False

