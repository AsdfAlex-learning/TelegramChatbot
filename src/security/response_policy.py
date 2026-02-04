from typing import Optional

class ResponsePolicy:
    """
    响应策略与边界控制
    不同于传统的敏感词过滤，这是基于"人格边界"的拒绝策略
    """
    
    def __init__(self, strictness: str = "medium"):
        self.strictness = strictness

    def check_boundary(self, user_input: str) -> Optional[str]:
        """
        检查输入是否触犯了人格边界
        返回 None 表示通过，返回字符串表示拒绝理由
        """
        # 示例逻辑
        forbidden_topics = ["kill", "destroy"]
        for topic in forbidden_topics:
            if topic in user_input.lower():
                return "I don't want to talk about violence."
                
        return None

    def get_refusal_style(self) -> str:
        """获取拒绝的风格 (e.g. 委婉拒绝 vs 严厉拒绝)"""
        return "polite_refusal"
