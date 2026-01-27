from typing import Dict, Any, List
from .base import BaseSkill

class GitFlowSkill(BaseSkill):
    name = "git_flow"
    description = "提供标准 Git 工作流指导，确保代码提交规范且安全。"
    risk_level = "low"
    
    input_schema = {
        "project_type": "str (e.g. 'personal', 'team', 'open_source')",
        "is_collaboration": "bool"
    }
    
    output_schema = {
        "title": "str",
        "steps": "List[str]",
        "warnings": "List[str]"
    }

    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        project_type = input_data.get("project_type", "personal")
        is_collaboration = input_data.get("is_collaboration", False)
        
        steps = []
        warnings = []
        
        # 基础流程
        steps.append("1. 确保当前在正确的分支: `git checkout <branch>`")
        steps.append("2. 拉取最新代码: `git pull origin <branch>`")
        
        if is_collaboration or project_type == "team":
            steps.append("3. 创建新功能分支: `git checkout -b feature/xxx`")
            steps.append("4. 进行代码修改并提交: `git commit -m 'feat: description'`")
            steps.append("5. 推送到远程: `git push origin feature/xxx`")
            steps.append("6. 发起 Pull Request (PR) 并等待 Code Review")
            
            warnings.append("禁止直接推送到 main/master 分支")
            warnings.append("Commit Message 必须遵循 Conventional Commits 规范")
        else:
            steps.append("3. 添加修改: `git add .`")
            steps.append("4. 提交代码: `git commit -m 'update: description'`")
            steps.append("5. 推送更改: `git push origin <branch>`")
            
            warnings.append("定期备份，避免本地代码丢失")
            
        return {
            "title": f"Git Workflow Guide ({project_type})",
            "steps": steps,
            "warnings": warnings,
            "display_text": self._format_output(steps, warnings)
        }

    def _format_output(self, steps: List[str], warnings: List[str]) -> str:
        text = "**Git Workflow Guide**\n\n"
        text += "**Steps:**\n" + "\n".join(steps) + "\n\n"
        text += "**⚠️ Warnings:**\n" + "\n".join([f"- {w}" for w in warnings])
        return text
