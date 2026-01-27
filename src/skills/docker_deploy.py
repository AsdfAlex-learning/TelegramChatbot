from typing import Dict, Any, List
from .base import BaseSkill

class DockerDeploySkill(BaseSkill):
    name = "docker_deploy"
    description = "生成 Docker 部署检查清单，确保生产环境配置安全合规。"
    risk_level = "medium"
    
    input_schema = {
        "language": "str (e.g. 'python', 'node', 'go')",
        "is_production": "bool"
    }
    
    output_schema = {
        "checklist": "List[str]",
        "base_image_recommendation": "str",
        "security_notes": "List[str]"
    }

    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        language = input_data.get("language", "python").lower()
        is_production = input_data.get("is_production", False)
        
        checklist = [
            "创建 .dockerignore 文件，排除 .git, __pycache__, .env 等文件",
            "设置正确的工作目录 (WORKDIR)",
            "使用非 root 用户运行应用 (USER appuser)"
        ]
        
        security_notes = []
        base_image = ""
        
        # 语言特定配置
        if "python" in language:
            base_image = "python:3.11-slim-bullseye (Recommended for size/stability)"
            checklist.append("使用 pip install --no-cache-dir 减小镜像体积")
            checklist.append("复制 requirements.txt 并安装依赖")
        elif "node" in language:
            base_image = "node:18-alpine"
            checklist.append("使用 npm ci 替代 npm install")
            checklist.append("设置 NODE_ENV=production")
        elif "go" in language:
            base_image = "golang:1.21-alpine (Build) -> scratch/alpine (Runtime)"
            checklist.append("使用多阶段构建 (Multi-stage build)")
            
        # 生产环境特定配置
        if is_production:
            checklist.append("确保没有敏感环境变量 (Secrets) 硬编码在 Dockerfile 中")
            checklist.append("配置健康检查 (HEALTHCHECK)")
            checklist.append("设置资源限制 (CPU/Memory limits)")
            
            security_notes.append("❌ 禁止使用 'latest' 标签，必须锁定具体版本号")
            security_notes.append("❌ 禁止在镜像中包含 SSH keys 或 API tokens")
            security_notes.append("✅ 建议扫描镜像漏洞 (trivy/snyk)")
        else:
            checklist.append("开发环境可挂载源代码卷 (Volume) 以支持热重载")
            
        return {
            "checklist": checklist,
            "base_image_recommendation": base_image,
            "security_notes": security_notes,
            "display_text": self._format_output(checklist, base_image, security_notes)
        }

    def _format_output(self, checklist, base_image, notes) -> str:
        text = "**Docker Deployment Checklist**\n\n"
        text += f"**Base Image:** `{base_image}`\n\n"
        text += "**Checklist:**\n" + "\n".join([f"- [ ] {item}" for item in checklist]) + "\n\n"
        if notes:
            text += "**🛡️ Security Notes:**\n" + "\n".join([f"- {note}" for note in notes])
        return text
