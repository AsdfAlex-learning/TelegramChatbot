import telebot
import requests
import time
from src.core.logger import get_logger
from src.core.config_loader import ConfigLoader

# =============================================================================
# [Telegram Client] 技术细节层
# 职责：负责 TeleBot 的初始化、网络请求封装、错误重试。
# 规则：
# 1. 这里只包含“怎么发消息”、“怎么连 Telegram”的技术代码。
# 2. 不应该包含任何业务逻辑（如“用户说了什么怎么回复”）。
# 3. 提供 safe_send_message 这样的工具函数。
# =============================================================================

logger = get_logger("TelegramClient")

# Review Note: 这里独立实例化 ConfigLoader 是安全的，因为它是读取静态文件。
# 为了避免循环依赖，我们不从 wiring 导入 config。
config_loader = ConfigLoader()
TELEGRAM_TOKEN = config_loader.system_config.telegram.bot_token

# Review Note: tb_bot 是一个全局单例。
# 这种做法方便了 handlers.py 使用装饰器 (@tb_bot.message_handler)，
# 但也导致了强耦合。在大型项目中，通常会用依赖注入容器来管理 Bot 实例。
tb_bot = telebot.TeleBot(TELEGRAM_TOKEN)

def safe_send_message(chat_id, text, max_attempts=3):
    """
    安全发送消息，包含重试机制。
    这是纯 IO 操作的封装。
    """
    backoff = 1
    for attempt in range(max_attempts):
        try:
            tb_bot.send_message(chat_id, text)
            return True
        except requests.exceptions.RequestException as e:
            if attempt == max_attempts - 1:
                logger.error(f"[TELEGRAM] 发送失败 | chat_id: {chat_id} | error: {e}")
                return False
            time.sleep(backoff)
            backoff = min(backoff * 2, 10)
        except Exception as e:
            logger.error(f"[TELEGRAM] 发送错误 | chat_id: {chat_id} | error: {e}")
            return False
