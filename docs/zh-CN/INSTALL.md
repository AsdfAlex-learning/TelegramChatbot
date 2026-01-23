# 安装与运行说明

## 环境要求

- **Conda**: 必须安装 Anaconda 或 Miniconda
- **Python**: 3.12 (通过 Conda 环境管理)

## 快速开始

### 1. 创建并激活 Conda 环境

```powershell
# 1. 创建环境 (使用项目根目录下的 environment.yaml)
conda env create -f environment.yaml

# 2. 激活环境
conda activate telegram_chatbot
```

### 2. 验证安装

```powershell
python --version
# 应输出 Python 3.12.x
```

### 3. 配置密钥与设置

- 请参考 `config/example_system.yaml` 创建或修改配置。
- 确保 API Key 等敏感信息已正确填入。

### 4. 运行项目

**启动 Bot 主程序**：

```powershell
python src/bot/run.py
```

**启动 LLM 服务 (后续开发)**：

```powershell
# 此时还未实现，仅作预留
# uvicorn src.llm_system.server.app:app --host 0.0.0.0 --port 8000
```

---

> **注意**: 本项目已完全移除 NoneBot 依赖，转为纯 Python 架构。请勿使用 `nb run` 启动。
