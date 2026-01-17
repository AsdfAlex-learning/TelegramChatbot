from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional

# ================== System Config Models (system.yaml) ==================

class TelegramConfig(BaseModel):
    bot_token: str = Field(..., description="Telegram Bot Token")
    owner_id: int = Field(default=0, description="Owner Telegram User ID for absolute control")

class LLMConfig(BaseModel):
    api_key: str = Field(..., description="OpenAI Compatible API Key")
    api_url: str = Field(default="https://api.deepseek.com/chat/completions", description="API URL")
    model: str = Field(default="deepseek-chat", description="Model name")
    temperature: float = Field(default=0.7, description="Sampling temperature")
    max_tokens: int = Field(default=1024, description="Max tokens for response")

class BotConfig(BaseModel):
    private_mode_default: bool = Field(default=True, description="Default private mode state")

class MessageBufferConfig(BaseModel):
    collect_min_time: int = Field(default=15, description="Min collection time (seconds)")
    collect_max_time: int = Field(default=20, description="Max collection time (seconds)")

class SystemConfig(BaseModel):
    telegram: TelegramConfig
    llm: LLMConfig
    bot: BotConfig = Field(default_factory=BotConfig)
    message_buffer: MessageBufferConfig = Field(default_factory=MessageBufferConfig)

# ================== AI Rules Models (ai_rules.yaml) ==================

class AIRulesConfig(BaseModel):
    rules: List[str] = Field(default_factory=list, description="List of system-level AI rules")

    def format(self) -> str:
        return "\n".join([f"- {rule}" for rule in self.rules])

# ================== Persona Models (persona.yaml) ==================

class IdentityConfig(BaseModel):
    name: str
    description: str

class RelationshipConfig(BaseModel):
    type: str
    closeness: str
    power_distance: str

class PersonalityConfig(BaseModel):
    emotionality: str
    stability: str
    initiative: str

class LanguageStyleConfig(BaseModel):
    tone: str
    fillers: List[str]
    punctuation: str

class PersonaSettings(BaseModel):
    identity: IdentityConfig
    relationship: RelationshipConfig
    personality: PersonalityConfig
    language_style: LanguageStyleConfig
    boundaries: List[str] = Field(default_factory=list)

    def format(self) -> str:
        lines = []
        lines.append(f"姓名: {self.identity.name}")
        lines.append(f"设定: {self.identity.description}")
        
        lines.append(f"关系类型: {self.relationship.type}")
        lines.append(f"亲密度: {self.relationship.closeness}")
        lines.append(f"权力距离: {self.relationship.power_distance}")
        
        lines.append(f"性格特征: 感性度({self.personality.emotionality}), 稳定性({self.personality.stability}), 主动性({self.personality.initiative})")
        
        lines.append(f"语言风格: {self.language_style.tone}")
        lines.append(f"口癖/填充词: {', '.join(self.language_style.fillers)}")
        lines.append(f"标点习惯: {self.language_style.punctuation}")
        
        if self.boundaries:
            lines.append("行为边界:")
            for b in self.boundaries:
                lines.append(f"  - {b}")
        return "\n".join(lines)

class PersonaConfig(BaseModel):
    # Allow dynamic keys for different personas, 'default' is required
    default: PersonaSettings
    extra_personas: Dict[str, PersonaSettings] = Field(default_factory=dict)

    def __init__(self, **data):
        # Handle 'default' explicitly, put others in extra_personas
        default_data = data.pop('default', None)
        if default_data is None:
             raise ValueError("persona.yaml must contain 'default' key")
        
        super().__init__(default=default_data, extra_personas=data)

# ================== API Config Models ==================

class GlobalAPIConfig(BaseModel):
    api_settings: Dict[str, Any] = Field(default_factory=dict)

