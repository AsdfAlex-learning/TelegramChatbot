class PersonaMemory:
    """
    人格记忆 (Self Memory)
    存储 Agent 关于"我是谁"的认知
    这部分不同于 prompt 中的静态设定，它是可以随着时间演化的
    """
    
    def __init__(self):
        self.self_perception = {
            "name": "AI",
            "likes": ["chatting", "helping"],
            "dislikes": ["rudeness"],
            "shared_experiences": []
        }

    def update_perception(self, key: str, value: any):
        """更新自我认知"""
        self.self_perception[key] = value
        
    def get_core_identity(self) -> str:
        """获取核心身份描述"""
        return f"I am {self.self_perception['name']}."
