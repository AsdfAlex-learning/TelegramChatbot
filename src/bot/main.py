import time
from src.core.logger import get_logger

# 1. 引入 Wiring (核心对象组装)
import src.bot.wiring

# 2. 引入 Handlers (注册 Telegram 回调)
import src.bot.telegram.handlers

# 3. 引入 Polling (启动 Telegram 循环)
from src.bot.telegram.polling import start_polling_thread

logger = get_logger("Main")

def main():
    logger.info("🚀 正在初始化 Telegram Chatbot...")
    
    # 启动后台轮询线程
    start_polling_thread()
    
    logger.info("✅ 机器人已启动！(按 Ctrl+C 停止)")
    
    # 主线程阻塞
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("🛑 正在停止机器人...")
    except Exception as e:
        logger.error(f"❌ 运行时发生错误: {e}")
        raise
