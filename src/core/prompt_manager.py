"""
文件职责：Prompt 管理器
负责加载 Prompt 模板，并将系统规则、人设、记忆、对话历史和用户输入
组装成最终发送给 LLM 的 Prompt 字符串。
"""

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
            raise FileNotFoundError(f"未找到 Prompt 模板: {self.template_path}")
        with open(self.template_path, 'r', encoding='utf-8') as f:
            return f.read()

    def build_prompt(self, user_message: str, memory: str = "暂无", conversation: str = "暂无") -> str:
        """
        使用模板构建最终 Prompt。
        """
        # 可选：重新加载模板（开发模式下很有用）
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
