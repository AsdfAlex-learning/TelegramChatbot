from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any

class EmotionType(Enum):
    NEUTRAL = "neutral"
    HAPPY = "happy"
    SAD = "sad"
    ANGRY = "angry"
    SHY = "shy"
    EXCITED = "excited"

class RelationshipStage(Enum):
    STRANGER = "stranger"
    ACQUAINTANCE = "acquaintance"
    FRIEND = "friend"
    CLOSE_FRIEND = "close_friend"
    PARTNER = "partner"

@dataclass
class PersonaState:
    """
    人格状态模型
    维护 Agent 的核心情绪和关系状态
    """
    # 核心情绪维度
    current_emotion: EmotionType = EmotionType.NEUTRAL
    arousal_level: float = 0.5  # 唤醒度 0.0 - 1.0
    valence_level: float = 0.5  # 愉悦度 0.0 - 1.0
    
    # 关系状态
    relationship_stage: RelationshipStage = RelationshipStage.STRANGER
    intimacy_level: int = 0  # 亲密度数值
    
    # 短期状态标志
    is_tired: bool = False
    is_busy: bool = False
    
    def update_emotion(self, emotion: EmotionType, arousal: float = None):
        """更新当前情绪"""
        self.current_emotion = emotion
        if arousal is not None:
            self.arousal_level = arousal
            
    def to_dict(self) -> Dict[str, Any]:
        return {
            "emotion": self.current_emotion.value,
            "arousal": self.arousal_level,
            "relationship": self.relationship_stage.value,
            "intimacy": self.intimacy_level
        }
