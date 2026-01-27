# Skills Module

该模块提供了一组 **确定性、可控、可审计** 的能力单元 ("Skills")，用于处理高风险或需要标准输出的场景。

## 核心理念
- **Skills ≠ Prompt 模板**: Skill 是包含业务逻辑的代码单元。
- **确定性输出**: Skill 不依赖 LLM 的随机生成，而是返回结构化的数据。
- **安全性**: Skill 不直接执行系统操作，只生成指导建议。

## 目录结构
- `base.py`: Skill 抽象基类。
- `registry.py`: Skill 注册中心，支持按名称或意图查找。
- `router_helper.py`: 辅助 Router 进行意图匹配和分发。
- `git_flow.py`: Git 工作流指导 Skill。
- `docker_deploy.py`: Docker 部署清单 Skill。
- `sql_security.py`: SQL 安全建议 Skill。

## 使用示例

```python
from src.skills import RouterHelper, SkillRegistry

# 假设 Router 识别到了意图
intent = "docker_deploy"
context = {"language": "python", "is_production": True}

# 匹配并执行
skill_name = RouterHelper.match_intent(intent)
if skill_name:
    success, result = RouterHelper.dispatch(skill_name, context)
    if success:
        print(result["display_text"])
```
