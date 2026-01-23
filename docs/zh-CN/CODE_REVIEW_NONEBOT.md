# NoneBot 依赖使用情况审查与重构建议

## 1. 现状分析：NoneBot 用哪了？

经过对全项目的代码扫描，NoneBot 目前仅在以下 3 个文件中出现：

### 1.1 `run.py` (根目录)
```python
import nonebot
nonebot.run()
```
**作用**：仅仅作为程序的启动器，启动了一个基于 FastAPI/Uvicorn 的 Web 服务进程。

### 1.2 `src/bot/main.py`
```python
import nonebot
from nonebot import get_driver

driver = get_driver()
@driver.on_startup
async def startup():
    start_polling_thread()
```
**作用**：
1.  利用 `on_startup` 钩子来启动我们的 Telegram 轮询线程。
2.  利用 NoneBot 的生命周期管理。

### 1.3 `src/bot/wiring.py`
```python
import nonebot
nonebot.init(env_file=...)
```
**作用**：
1.  加载 `.env` 环境变量。

---

## 2. 深度分析：我们真的需要它吗？

**答案：完全不需要。**

目前的架构中，NoneBot 处于一个非常尴尬的“僵尸”状态：

1.  **适配器未使用**：我们虽然安装了 `nonebot-adapter-telegram`，但实际代码完全使用的是 `pyTelegramBotAPI (telebot)` 进行 IO 操作。NoneBot 的适配器层完全被旁路了。
2.  **插件系统未使用**：我们自己实现了一套 `src.core.component_system`，完全没有使用 NoneBot 的 `load_plugin` 或 `matcher` 系统。
3.  **Web 服务冗余**：NoneBot 默认启动一个 Uvicorn Web Server。但我们的 Bot 是基于 `Polling`（长轮询）模式运行的，不需要监听 Webhook 端口。这意味着我们启动了一个 HTTP 服务器，却从来不处理任何 HTTP 请求。
4.  **配置加载冗余**：我们有自己的 `ConfigLoader`，NoneBot 的 `init` 仅仅是为了读取 `.env`，这完全可以用轻量级的 `python-dotenv` 替代。

### 依赖成本
为了保留这个没用的 NoneBot，我们引入了：
- `FastAPI` / `Starlette` (Web 框架)
- `Uvicorn` (ASGI 服务器)
- `Loguru` (日志库，虽然好用但我们有自己的 logger 封装)
- `Pydantic` (版本兼容性包袱)
- 一堆 NoneBot 的内部依赖

---

## 3. 重构方案：如何移除 NoneBot？

移除 NoneBot 非常简单，只需要替换掉“配置加载”和“主循环”两个功能。

### 步骤 1：清理依赖
在 `requirements.txt` 中直接移除 `nonebot` 相关依赖即可。
**注意**：由于你的配置全部写在 `system.yaml` 等配置文件中（包括 Token 和 API Key），且代码中 `ConfigLoader` 是直接读取 yaml 文件的，并没有使用环境变量，因此**不需要**引入 `python-dotenv`，也不需要加载 `.env` 文件。

### 步骤 2：改造 `src/bot/wiring.py`
**修改前**：
```python
import nonebot
nonebot.init(env_file=".env")
```

**修改后**：
直接删除上述两行代码。

### 步骤 3：改造 `src/bot/main.py` 和 `run.py`
我们不需要 NoneBot 的 Driver 来管理生命周期，只需要一个简单的 Python 脚本。

**新版 `run.py` 伪代码**：
```python
import time
from src.bot.wiring import bot_app
from src.bot.telegram.polling import start_polling_thread

def main():
    # 1. 加载配置 & 依赖 (在 wiring import 时自动完成)
    
    # 2. 启动轮询线程
    start_polling_thread()
    
    # 3. 主线程阻塞 (替代 nonebot.run())
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("停止运行")

if __name__ == "__main__":
    main()
```

## 4. 结论

**建议立即移除 NoneBot。**

目前的架构已经是完全独立的：
- **IO 层**：自建 (`src/bot/telegram/`)
- **业务层**：自建 (`src/bot/app.py`)
- **组件层**：自建 (`src/core/component_system/`)
- **配置层**：自建 (`src/core/config_loader.py`)

NoneBot 现在不仅没有提供帮助，反而在混淆视听（让人误以为这是个 NoneBot 插件），并增加了部署体积。移除它将使项目更加纯粹、轻量，并且完全符合我们刚刚重构的清晰架构。
