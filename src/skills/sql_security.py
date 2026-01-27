from typing import Dict, Any, List
from .base import BaseSkill

class SQLSecuritySkill(BaseSkill):
    name = "sql_security"
    description = "提供 SQL 安全编写建议，识别常见注入风险。"
    risk_level = "high" # 涉及数据库安全，定级为高
    
    input_schema = {
        "scenario": "str (描述使用场景，如 'user login', 'search by name')",
        "db_type": "str (optional, e.g. 'mysql', 'postgres')"
    }
    
    output_schema = {
        "recommendations": "List[str]",
        "risk_patterns": "List[str]",
        "example_safe_pattern": "str"
    }

    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        scenario = input_data.get("scenario", "")
        
        recommendations = [
            "始终使用参数化查询 (Parameterized Queries) 或预编译语句 (Prepared Statements)",
            "最小权限原则：应用程序连接数据库的账号只应拥有必要的权限 (避免 GRANT ALL)",
            "输入验证：严格校验所有用户输入的数据类型和长度"
        ]
        
        risk_patterns = [
            "字符串拼接: `SELECT * FROM users WHERE name = '" + "user_input" + "'`",
            "直接格式化: `f'SELECT * FROM items WHERE id = {id}'`",
            "ORM 原始查询未过滤: `User.objects.raw(f'...')`"
        ]
        
        example_safe = ""
        
        if "login" in scenario.lower():
            example_safe = "cursor.execute('SELECT id, password_hash FROM users WHERE email = %s', (email,))"
            recommendations.append("不要存储明文密码，使用 Argon2 或 bcrypt 哈希")
        elif "search" in scenario.lower():
            example_safe = "cursor.execute('SELECT * FROM products WHERE name LIKE %s', ('%' + keyword + '%',))"
            recommendations.append("对于模糊搜索，注意通配符的转义处理")
        else:
            example_safe = "cursor.execute('SELECT * FROM table WHERE id = %s', (user_id,))"
            
        return {
            "recommendations": recommendations,
            "risk_patterns": risk_patterns,
            "example_safe_pattern": example_safe,
            "display_text": self._format_output(recommendations, risk_patterns, example_safe)
        }

    def _format_output(self, recs, risks, example) -> str:
        text = "**SQL Security Advisory**\n\n"
        text += "**✅ Recommendations:**\n" + "\n".join([f"- {r}" for r in recs]) + "\n\n"
        text += "**❌ Common Risk Patterns (DO NOT USE):**\n" + "\n".join([f"- {r}" for r in risks]) + "\n\n"
        text += "**💡 Safe Example:**\n```python\n" + example + "\n```"
        return text
