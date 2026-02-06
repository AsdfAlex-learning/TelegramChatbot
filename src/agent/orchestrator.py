from dataclasses import dataclass, field
from typing import Dict, Any, Optional
import random

from src.agent.state import PersonaState
from src.agent.empathy_planner import EmpathyPlanner, ExpressionPlan, TextStrategy, BodyAction

# Text Skills
from src.skills.text.short_reply import short_reply_strategy
from src.skills.text.long_reply import long_emotional_reply_strategy
from src.skills.text.comfort import comfort_reply_strategy

# Body Language Skills
from src.skills.body_language.idle import idle_action
from src.skills.body_language.nod import nod_action
from src.skills.body_language.shy import shy_action
from src.skills.body_language.tilt_head import tilt_head_action
from src.skills.body_language.wave import wave_action

@dataclass
class AgentResponse:
    """
    Agent 的最终表达结果
    包含：说什么(text)、做什么(action)、怎么说(voice/mood)
    """
    text: str
    action: str
    mood: str
    delay_ms: int
    voice_params: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "action": self.action,
            "mood": self.mood,
            "delay_ms": self.delay_ms,
            "voice": self.voice_params
        }

class ExpressionOrchestrator:
    """
    多模态表达编排器 (The Conductor)
    
    职责：
    1. 接收 Planner 的 ExpressionPlan
    2. 调用 Text Skills 获取生成策略
    3. 调用 Body Skills 获取动作指令
    4. (模拟) 生成最终文本
    5. 组装成 AgentResponse
    """
    
    def __init__(self, planner: EmpathyPlanner):
        self.planner = planner
        # 未来这里会注入 LLM Client
        # self.llm_client = ...

    async def orchestrate_response(self, user_input: str, state: PersonaState) -> Optional[AgentResponse]:
        """
        编排一次完整的响应
        """
        # 1. 获取决策计划
        plan = self.planner.plan_response(user_input, state)
        
        # 如果策略是保持沉默，则不返回响应
        if not plan.should_reply or plan.text_strategy == TextStrategy.SILENCE:
            return None
            
        # 2. 执行 Body Language Skill
        action_name = self._execute_body_skill(plan.body_action)
        
        # 3. 执行 Text Skill (获取生成策略)
        text_config = self._execute_text_skill(plan.text_strategy, user_input)
        
        # 4. 生成文本 (这里暂时使用 Mock 生成，未来连接 LLM)
        generated_text = await self._mock_llm_generation(text_config, user_input)
        
        # 5. 组装最终响应
        response = AgentResponse(
            text=generated_text,
            action=action_name,
            mood=plan.mood.value,
            delay_ms=plan.delay_ms,
            voice_params={"tone": plan.mood.value} # 简单示例
        )
        
        return response

    def _execute_body_skill(self, action_type: BodyAction) -> str:
        """根据动作类型调用对应的 Skill 函数"""
        if action_type == BodyAction.IDLE:
            return idle_action()
        elif action_type == BodyAction.NOD:
            return nod_action()
        elif action_type == BodyAction.SHY:
            return shy_action()
        elif action_type == BodyAction.TILT_HEAD:
            return tilt_head_action()
        elif action_type == BodyAction.WAVE:
            return wave_action()
        else:
            return idle_action()

    def _execute_text_skill(self, strategy_type: TextStrategy, context: str) -> Dict[str, Any]:
        """根据文本策略调用对应的 Skill 函数获取配置"""
        if strategy_type == TextStrategy.SHORT_REPLY:
            return short_reply_strategy(context)
        elif strategy_type == TextStrategy.LONG_REPLY:
            return long_emotional_reply_strategy(context)
        elif strategy_type == TextStrategy.COMFORT:
            return comfort_reply_strategy(context)
        else:
            return short_reply_strategy(context)

    async def _mock_llm_generation(self, config: Dict[str, Any], context: str) -> str:
        """
        模拟 LLM 生成过程
        实际项目中这里会调用 self.llm_client.chat_completion(...)
        """
        style = config.get("style_instruction", "")
        max_tokens = config.get("max_tokens", 50)
        
        # 简单的 Mock 逻辑
        if "brief" in style:
            candidates = ["嗯嗯，知道了。", "好的哦。", "收到！", "确实是这样呢。"]
        elif "emotional" in style:
            candidates = [
                "听你这么说，我感觉也能理解你的心情... 这种事情确实让人很在意呢。",
                "真的吗？我也好想知道更多细节呀，快跟我说说！",
                "其实我也一直这么觉得，这种感觉很奇妙对吧？"
            ]
        elif "comfort" in style:
            candidates = [
                "别难过啦，我会一直陪着你的。",
                "抱抱你... 一切都会好起来的。",
                "如果不开心的话，随时都可以和我说哦。"
            ]
        else:
            candidates = ["(Agent 正在思考...)"]
            
        return random.choice(candidates)
