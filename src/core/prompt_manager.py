import os
from typing import Optional, List
from src.core.config import AIRulesConfig, PersonaSettings

class PromptManager:
    def __init__(self, template_path: str, ai_rules: AIRulesConfig, persona_settings: PersonaSettings):
        self.template_path = template_path
        self.ai_rules = ai_rules
        self.persona = persona_settings
        self.template = self._load_template()

    def _load_template(self) -> str:
        if not os.path.exists(self.template_path):
            raise FileNotFoundError(f"Prompt template not found: {self.template_path}")
        with open(self.template_path, 'r', encoding='utf-8') as f:
            return f.read()

    def build_prompt(self, user_message: str, memory: str = "暂无", conversation: str = "暂无") -> str:
        """
        Constructs the final prompt using the template.
        """
        # Reload template in case it changed (optional, but good for dev)
        # self.template = self._load_template() 
        
        system_rules_str = self.ai_rules.format()
        persona_str = self.persona.format()
        
        prompt = self.template
        prompt = prompt.replace("{{system_rules}}", system_rules_str)
        prompt = prompt.replace("{{persona}}", persona_str)
        prompt = prompt.replace("{{memory}}", memory)
        prompt = prompt.replace("{{conversation}}", conversation)
        prompt = prompt.replace("{{user_message}}", user_message)
        
        return prompt
