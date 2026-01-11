from pydantic import BaseModel, Field
from typing import Dict, Any, Optional

# ================== Main Config Models ==================

class TelegramConfig(BaseModel):
    bot_token: str = Field(..., description="Telegram Bot Token")

class DeepSeekConfig(BaseModel):
    api_key: str = Field(..., description="DeepSeek API Key")
    api_url: str = Field(default="https://api.deepseek.com/chat/completions", description="DeepSeek API URL")

class SystemPromptConfig(BaseModel):
    core_rules: str = Field(default="", description="Core rules for the bot")
    default_persona: str = Field(default="", description="Default persona description")

class AppConfig(BaseModel):
    telegram: TelegramConfig
    deepseek: DeepSeekConfig
    system_prompt: SystemPromptConfig
    persona_card: Dict[str, str] = Field(default_factory=dict, description="Dictionary of persona cards")

# ================== API Config Models ==================

class GlobalAPIConfig(BaseModel):
    api_settings: Dict[str, Any] = Field(default_factory=dict)
