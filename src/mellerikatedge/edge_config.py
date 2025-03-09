import threading
import mellerikatedge.edge_utils as edge_utils

from loguru import logger

class EdgeConfig:
    _instance = None
    _lock = threading.Lock()

    SOLUTION_DIR = "solution_dir"
    ALO_VERSION = "alo_version"
    EDGECOND_URL = "edge_conductor_url"

    EDGECOND_LOCATION = "edge_conductor_location"
    EDGECOND_LOCATION_CLOUD = "cloud"
    EDGECOND_LOCATION_ONPREMISE = "onprimise"

    SECURITY_KEY = "edge_security_key"
    MODEL_INFO = "model_info"

    MODEL_SEQ = "model_seq"
    MODEL_VERSION = "model_version"
    STREAM_NAME = "stream_name"

    def init(cls, *args, **kwargs):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super().__new__(cls)
                    cls._instance.init()
        return cls._instance

    def init(self):
        logger.info("Init Config")

    def load_config(self, config_path):
        with self._lock:
            self.config = edge_utils.load_yaml(config_path)
            self.config_path = config_path
            logger.info("Load Config")
            logger.info(self.config)

    def save_config(self):
        with self._lock:
            edge_utils.save_yaml(self.config_path, self.config)

    def get_config(self, name):
        with self._lock:
            return self.config[name]

    def set_config(self, name, values):
        with self._lock:
            # logger.info(f"Update {name} - {values}")
            self.config[name] = values
