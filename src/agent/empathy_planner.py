from typing import List, Optional
from dataclasses import dataclass
from src.agent.state import PersonaState, EmotionType

@dataclass
class ExpressionPlan:
    """
    表达计划
    决定了 Agent "想怎么回应"
    """
    should_reply: bool = True
    delay_ms: int = 0  # 拟人化延迟
    target_emotion: EmotionType = EmotionType.NEUTRAL
    
    # 表达策略开关
    use_voice: bool = False
    use_live2d: bool = True
    tone_style: str = "normal"  # normal, soft, tsundere, etc.
    
    # 拒绝/冷处理策略
    rejection_reason: Optional[str] = None

class EmpathyPlanner:
    """
    情境/情绪/表达策略决策器 (The Prefrontal Cortex)
    
    它不负责生成具体的文本内容（那是 LLM 的工作），
    它负责决定：
    1. 这句话是否需要回应？
    2. 用什么情绪回应？
    3. 是否需要配合动作？
    4. 现在的关系阶段允许什么样的互动？
    """
    
    def __init__(self, persona_config: dict = None):
        self.config = persona_config or {}

    def plan_response(self, user_input: str, current_state: PersonaState) -> ExpressionPlan:
        """
        根据用户输入和当前状态，规划表达策略
        """
        # TODO: 这里未来会接入更复杂的逻辑或轻量级模型判断
        
        plan = ExpressionPlan()
        
        # 简单示例逻辑：
        # 如果用户很长，我们可能需要更长的延迟来"阅读"
        if len(user_input) > 20:
            plan.delay_ms = 1500
        else:
            plan.delay_ms = 500
            
        # 传递当前情绪作为目标情绪（或者根据输入改变情绪）
        plan.target_emotion = current_state.current_emotion
        
        return plan

    def should_reject(self, user_input: str, state: PersonaState) -> bool:
        """
        判断是否触犯了人格边界
        """
        # TODO: 实现安全/边界检查
        return False
