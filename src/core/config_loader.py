import os
import yaml
import logging
from src.core.config import SystemConfig, AIRulesConfig, PersonaConfig, GlobalAPIConfig
from src.core.prompt_manager import PromptManager

class ConfigLoader:
    _instance = None
    _system_config: SystemConfig = None
    _ai_rules_config: AIRulesConfig = None
    _persona_config: PersonaConfig = None
    _api_config: GlobalAPIConfig = None
    _prompt_manager: PromptManager = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigLoader, cls).__new__(cls)
            cls._instance.reload()
        return cls._instance

    def reload(self):
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        config_dir = os.path.join(project_root, "config")
        
        # 1. Load System Config
        system_path = os.path.join(config_dir, "system.yaml")
        self._system_config = self._load_yaml(system_path, SystemConfig)

        # 2. Load AI Rules
        rules_path = os.path.join(config_dir, "ai_rules.yaml")
        self._ai_rules_config = self._load_yaml(rules_path, AIRulesConfig)

        # 3. Load Persona
        persona_path = os.path.join(config_dir, "persona.yaml")
        self._persona_config = self._load_yaml(persona_path, PersonaConfig)

        # 4. Initialize PromptManager
        template_path = os.path.join(config_dir, "prompt_template.txt")
        # Use default persona for now
        self._prompt_manager = PromptManager(template_path, self._ai_rules_config, self._persona_config.default)

        # 5. Load API Config
        api_config_path = os.path.join(config_dir, "api_config", "global_config.yaml")
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

    def _load_yaml(self, path: str, model_class):
        if not os.path.exists(path):
            raise FileNotFoundError(f"Config file missing: {path}")
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            return model_class(**data)
        except Exception as e:
            logging.critical(f"Failed to load config {path}: {e}")
            raise

    @property
    def system_config(self) -> SystemConfig:
        return self._system_config
    
    @property
    def persona_config(self) -> PersonaConfig:
        return self._persona_config

    @property
    def prompt_manager(self) -> PromptManager:
        return self._prompt_manager

    @property
    def api_config(self) -> GlobalAPIConfig:
        return self._api_config
    
    # Backward compatibility for API registry
    def get_config(self, key=None):
        if key:
            return self._api_config.api_settings.get(key, {})
        return self._api_config.api_settings
