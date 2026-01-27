from typing import Dict, Any, Optional, Tuple
from .registry import SkillRegistry

class RouterHelper:
    """
    辅助 Router 与 Skills 模块交互的工具类。
    提供意图匹配和 Skill 执行的统一接口。
    """
    
    @staticmethod
    def match_intent(user_intent: str) -> Optional[str]:
        """
        根据用户意图查找对应的 Skill 名称。
        
        Args:
            user_intent: Router 识别出的意图字符串 (e.g., 'deploy_docker').
            
        Returns:
            Skill name if found, else None.
        """
        skill = SkillRegistry.get_skill_by_intent(user_intent)
        if skill:
            return skill.name
        return None

    @staticmethod
    def dispatch(skill_name: str, input_context: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """
        分发请求到指定的 Skill。
        
        Args:
            skill_name: 技能名称。
            input_context: 上下文数据，用于提取 Skill 所需的输入。
            
        Returns:
            (success, result_dict)
        """
        try:
            # 这里可以加入参数提取/映射逻辑
            # 目前假设 input_context 直接包含 Skill 所需参数
            result = SkillRegistry.run(skill_name, input_context)
            
            # 检查是否执行失败
            if result.get("status") == "failed":
                return False, result
                
            return True, result
        except Exception as e:
            return False, {"error": str(e), "skill": skill_name}
