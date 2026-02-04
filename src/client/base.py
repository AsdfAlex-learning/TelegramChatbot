from abc import ABC, abstractmethod
from typing import Any, Optional

class BaseRenderer(ABC):
    """
    渲染器基类
    负责将抽象的表达内容（文本、动作）转换为特定平台的格式
    """
    @abstractmethod
    def render(self, content: Any) -> Any:
        pass

class BaseClient(ABC):
    """
    客户端基类 (Input/Output Adapter)
    抽象了具体的通信渠道（Telegram, Discord, Web等）
    """
    
    @abstractmethod
    async def send_text(self, target_id: str, text: str):
        """发送纯文本"""
        pass
        
    @abstractmethod
    async def send_action(self, target_id: str, action_name: str):
        """发送/触发动作 (如 Sticker 或 Live2D 指令)"""
        pass
        
    @abstractmethod
    async def send_voice(self, target_id: str, audio_data: bytes):
        """发送语音"""
        pass
