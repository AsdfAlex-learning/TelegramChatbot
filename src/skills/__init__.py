"""
Skills Module for Local LLM System.

该模块提供了一组确定性、可控的"技能"，用于处理高风险或需要标准输出的场景。
Skills 不直接执行系统命令，而是返回结构化的指导信息。

Core Components:
- BaseSkill: 所有 Skill 的基类。
- SkillRegistry: 负责注册和查找 Skill。
- RouterHelper: 辅助 Router 进行意图匹配和分发。

Available Skills:
- git_flow: Git 工作流指导。
- docker_deploy: Docker 部署清单生成。
- sql_security: SQL 安全建议。

Usage Example (Router):

    from src.skills import SkillRegistry, RouterHelper
    
    # 1. 注册 Skills (通常在应用启动时完成)
    from src.skills.git_flow import GitFlowSkill
    SkillRegistry.register(GitFlowSkill(), intents=["git_help", "git_workflow"])

    # 2. Router 逻辑
    intent = "git_workflow"
    skill_name = RouterHelper.match_intent(intent)
    
    if skill_name:
        success, result = RouterHelper.dispatch(skill_name, {"project_type": "team"})
        if success:
            return result["display_text"]
"""

from .base import BaseSkill
from .registry import SkillRegistry
from .router_helper import RouterHelper
from .git_flow import GitFlowSkill
from .docker_deploy import DockerDeploySkill
from .sql_security import SQLSecuritySkill

# 自动注册内置 Skills
SkillRegistry.register(GitFlowSkill(), intents=["git_guide", "git_flow", "git_workflow"])
SkillRegistry.register(DockerDeploySkill(), intents=["docker_deploy", "docker_help", "container_setup"])
SkillRegistry.register(SQLSecuritySkill(), intents=["sql_check", "sql_security", "db_safety"])

__all__ = [
    "BaseSkill",
    "SkillRegistry",
    "RouterHelper",
    "GitFlowSkill",
    "DockerDeploySkill",
    "SQLSecuritySkill"
]
