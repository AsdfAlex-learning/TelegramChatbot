import nonebot
from nonebot import get_driver

# =============================================================================
# [Main Entry] 程序入口
# 职责：负责框架启动和模块加载。
# 规则：
# 1. 这里是程序的起点，代码量应该极少。
# 2. 不包含任何业务逻辑。
# 3. 按照顺序加载：Wiring -> Handlers -> Polling -> NoneBot Run。
# =============================================================================

# 1. 引入 Wiring (核心对象组装)
# 这会初始化所有 Service, Controller, ComponentSystem
# Review Note: 这一步必须最先执行，确保所有单例和依赖都已准备好。
import src.bot.wiring

# 2. 引入 Handlers (注册 Telegram 回调)
# 必须在 bot 启动前注册，否则消息来了没人处理。
# Review Note: Handlers 依赖 Wiring 中的 bot_app 和 Client 中的 tb_bot。
import src.bot.telegram.handlers

# 3. 引入 Polling (启动 Telegram 循环)
from src.bot.telegram.polling import start_polling_thread

# 4. 框架启动逻辑
driver = get_driver()

@driver.on_startup
async def startup():
    # 启动 Telegram 轮询线程
    start_polling_thread()

if __name__ == "__main__":
    nonebot.run()
