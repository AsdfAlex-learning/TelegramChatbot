import os
import json
import logging

class ConfigLoader:
    _instance = None
    _config = {}
    _config_path = ""

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigLoader, cls).__new__(cls)
            cls._instance._load_config()
        return cls._instance

    def _load_config(self):
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self._config_path = os.path.join(project_root, "config", "api_config", "global_config.json")
        
        if not os.path.exists(self._config_path):
            logging.warning(f"Config file not found at {self._config_path}, creating default.")
            self._create_default_config()
        
        try:
            with open(self._config_path, 'r', encoding='utf-8') as f:
                self._config = json.load(f)
        except Exception as e:
            logging.error(f"Failed to load config: {e}")
            self._config = {}

    def _create_default_config(self):
        default_config = {
            "api_settings": {}
        }
        os.makedirs(os.path.dirname(self._config_path), exist_ok=True)
        with open(self._config_path, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, indent=4)
        self._config = default_config

    def get_config(self, key=None):
        if key:
            return self._config.get("api_settings", {}).get(key, {})
        return self._config.get("api_settings", {})

    def reload(self):
        self._load_config()
