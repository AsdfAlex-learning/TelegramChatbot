from typing import Any, Dict
from src.agent.state import PersonaState
from src.agent.empathy_planner import EmpathyPlanner, ExpressionPlan
# 假设未来会有 Client 抽象
# from src.client.base import BaseClient 

class ExpressionOrchestrator:
    """
    多模态表达编排器 (The Conductor)
    
    负责协调：
    - 文本生成 (LLM)
    - 动作执行 (Live2D)
    - 语音合成 (TTS)
    确保 动作 表情 语音 三者是同步的。

    """
    
    def __init__(self, planner: EmpathyPlanner):
        self.planner = planner
        # self.client = client # 绑定的输出端

    async def orchestrate_response(self, user_input: str, state: PersonaState):
        """
        编排一次完整的响应
        """
        # 1. 规划阶段 (Think before act)
        plan = self.planner.plan_response(user_input, state)
        
        if not plan.should_reply:
            return None
            
        # 2. 这里的逻辑未来会变得复杂：
        # - 并行调用 LLM 生成文本
        # - 并行选择 Live2D 动作
        # - 并在 Client 端同步渲染
        
        # 占位返回，实际应调用 Client.render(...)
        return {
            "text": "（思考中...）", # 这里应该是由 LLM 生成的内容
            "action": plan.target_emotion.value,
            "delay": plan.delay_ms
        }

    def determine_skills(self, plan: ExpressionPlan) -> list:
        """
        根据计划决定使用哪些 'Body Capabilities' (Skills)
        """
        skills = []
        if plan.use_live2d:
            # 根据情绪选择动作技能
            pass
        return skills
