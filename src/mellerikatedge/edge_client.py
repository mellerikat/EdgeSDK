import os
import requests
from .version import __version__
import mellerikatedge.edge_utils as edge_utils

import json
import asyncio
import nest_asyncio
import websockets

import threading

from datetime import datetime, timezone

from loguru import logger


class EdgeClient:
    url = None
    websocket_url = None
    jwt_token = None
    websocket = None

    def __init__(self, edge_app, config):
        self.edge_app = edge_app
        nest_asyncio.apply()

        self.url = edge_utils.remove_trailing_slash(config[edge_utils.CONFIG_EDGE_COND_URL])
        self.security_key = config[edge_utils.CONFIG_EDGE_SECURITY_KEY]
        if config[edge_utils.CONFIG_EDGE_COND_LOCATION] == edge_utils.CONFIG_EDGE_COND_LOCATION_CLOUD:
            self.websocket_url = f"wss://{edge_utils.remove_http_https(self.url)}/app/api/v1/socket/{self.security_key}"
        else:
            self.websocket_url = f"ws://{edge_utils.remove_http_https(self.url)}/app/api/v1/socket/{self.security_key}"


        self.websocket = None
        self.loop = asyncio.new_event_loop()
        self.thread = None
        self._stop_event = asyncio.Event()  # 종료 신호 추가
        logger.info(f"WebSocket URL: {self.websocket_url}")

    async def connect_edgeconductor(self):
        headers = {"Authorization": f"Bearer {self.jwt_token}"}
        while not self._stop_event.is_set():  # 종료 신호 확인
            try:
                self.websocket = await websockets.connect(self.websocket_url, extra_headers=headers)
                logger.info('WebSocket connected')
                asyncio.create_task(self._receive_messages())
                asyncio.create_task(self._keep_alive())
                await self._stop_event.wait()  # 종료 신호를 기다림
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
                    self.edge_app.receive_deploy_model(deploy_model)
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
        self.triedConnection = True
        if self.thread is None or not self.thread.is_alive():
            self.thread = threading.Thread(target=self.run_loop, daemon=True)
            self.thread.start()
            logger.info("WebSocket thread started")

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
            "note": "Edge SDK",
            "security_key": self.security_key,
            "device_mac": device_info["device_mac"],
            "device_os": device_info["device_os"],
            "device_cpu": device_info["device_cpu"],
            "device_gpu": device_info["device_gpu"]
        }

        response = requests.post(url, json=data)

        # 응답 확인
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

            return edge_details#deployed_info, deploy_model

        else:
            logger.error("GET Failed!")
            return None, None

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
                file_name = f"model.tar.gz"  # 기본 파일명 생성

            # logger.info(response.headers.get('Content-Disposition'))
            # file_name = response.headers.get('Content-Disposition').split('filename=')[-1]
            file_path = os.path.join(download_dir, 'model.tar.gz')
            with open(file_path, 'wb') as file:
                for chunk in response.iter_content(chunk_size=8192):
                    file.write(chunk)
            logger.info(f"{file_name} downloaded successfully. {file_path}")
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
            logger.info(f"metadata")
            with open(file_path, 'w') as file:
                json.dump(metadata, file, indent=2)
            logger.info(f"meta.json downloaded successfully. {file_path}")
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
        else:
            logger.error("Failed to update inference status:", response.status_code, response.text)

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

        # POST 요청 전송
        response = requests.post(url, headers=headers, files=files)
        if response.status_code == 201:
            logger.info("Successfully updated deploy result.")
        else:
            logger.error("Failed to update deploy result:", response.status_code, response.text)

        # 열려 있는 파일 객체를 닫기
        files["file"].close()