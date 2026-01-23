import sys
import os
import nonebot

# 1. 确保项目根目录在 PYTHONPATH 中
# 这样可以确保 import src.xxx 始终有效，无论从哪里运行此脚本
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.core.logger import get_logger

# 2. 引入 Bot 的核心逻辑
# 这会触发 wiring(组装)、handlers(注册)、polling(钩子) 的加载
import src.bot.main

logger = get_logger("Entry")

if __name__ == "__main__":
    logger.info("🚀 正在启动 Telegram Chatbot...")
    try:
        # 3. 启动 NoneBot 框架
        # 这会接管主线程，并触发 driver.on_startup 钩子
        nonebot.run()
    except Exception as e:
        logger.error(f"❌ 程序运行崩溃: {e}")
        raise
