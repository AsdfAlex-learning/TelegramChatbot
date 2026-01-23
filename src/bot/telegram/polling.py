import threading
import time
import requests
from src.core.logger import get_logger
from src.bot.telegram.client import tb_bot

# =============================================================================
# [Telegram Polling] 轮询服务
# 职责：负责维持与 Telegram 服务器的长连接。
# 规则：
# 1. 处理网络异常和重试。
# 2. 作为一个后台守护线程运行。
# =============================================================================

logger = get_logger("TelegramPolling")

def start_telegram_polling():
    logger.info("[TELEGRAM] 开始轮询 (Polling Start)")
    backoff = 1
    while True:
        try:
            # Review Note: timeout=90, long_polling_timeout=60 是经验值，
            # 确保长轮询连接稳定，减少频繁重连。
            tb_bot.polling(none_stop=True, timeout=90, long_polling_timeout=60)
            backoff = 1
        except requests.exceptions.ReadTimeout:
            # 超时是正常的，重试即可
            continue
        except requests.exceptions.ConnectionError as e:
            logger.error(f"[TELEGRAM] 连接错误 (Connection Error) | error: {str(e)}")
        except Exception as e:
            logger.error(f"[TELEGRAM] 轮询异常 (Polling Error) | error: {str(e)}")
        
        # 指数退避策略，防止网络炸裂时死循环请求
        time.sleep(backoff)
        backoff = min(backoff * 2, 60)

def start_polling_thread():
    polling_thread = threading.Thread(target=start_telegram_polling, daemon=True)
    polling_thread.start()
