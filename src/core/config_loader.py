import os
import yaml
import logging
from src.core.config import AppConfig, GlobalAPIConfig

class ConfigLoader:
    _instance = None
    _app_config: AppConfig = None
    _api_config: GlobalAPIConfig = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigLoader, cls).__new__(cls)
            cls._instance.reload()
        return cls._instance

    def reload(self):
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        # Load Main Config (YAML)
        config_path = os.path.join(project_root, "config", "config.yaml")
        if not os.path.exists(config_path):
            logging.error(f"Config file missing: {config_path}")
            raise FileNotFoundError(f"Config file missing: {config_path}")
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            self._app_config = AppConfig(**data)
        except Exception as e:
            logging.critical(f"Failed to load app config: {e}")
            raise

        # Load API Config (YAML)
        api_config_path = os.path.join(project_root, "config", "api_config", "global_config.yaml")
        try:
            if os.path.exists(api_config_path):
                with open(api_config_path, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                self._api_config = GlobalAPIConfig(**data)
            else:
                self._api_config = GlobalAPIConfig()
        except Exception as e:
            logging.error(f"Failed to load API config: {e}")
            self._api_config = GlobalAPIConfig()

    @property
    def app_config(self) -> AppConfig:
        return self._app_config

    @property
    def api_config(self) -> GlobalAPIConfig:
        return self._api_config
    
    # Backward compatibility for API registry and ConfigLoader.get_config()
    def get_config(self, key=None):
        if key:
            return self._api_config.api_settings.get(key, {})
        return self._api_config.api_settings
