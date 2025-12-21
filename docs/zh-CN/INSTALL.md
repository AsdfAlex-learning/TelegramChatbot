# 安装与运行说明

最低要求

- Python 版本：3.9+

步骤

1. 创建并激活虚拟环境（建议）

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. 安装依赖

```powershell
pip install -U pip
pip install -r requirements.txt
```

3. 配置密钥与设置

- 编辑 `config/PROTECTED_INFO.json`，至少填入：
	- `TELEGRAM_TOKEN`
	- `DEEPSEEK_API_KEY`
	- `DEEPSEEK_API_URL`

- （可选）项目使用 `.env.prod` 作为 NoneBot 环境文件，如果需要环境变量请创建该文件或在系统环境中设置相应变量。

4. 运行项目

```powershell
python bot.py
```

如需帮助：请告诉我你在 Windows、Linux 还是容器中运行，以及是否需要我帮你自动安装依赖并运行一次测试。谢谢！

此项目是由一个心血来潮的零经验大学生进行维护的，有诸多不成熟的地方还请见谅！