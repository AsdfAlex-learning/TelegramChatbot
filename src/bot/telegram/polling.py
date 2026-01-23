import threading
import time
import requests
from src.core.logger import get_logger
from src.bot.telegram.client import tb_bot

logger = get_logger("TelegramPolling")

def start_telegram_polling():
    logger.info("[TELEGRAM] 开始轮询")
    backoff = 1
    while True:
        try:
            # timeout=90, long_polling_timeout=60 为经验值
            tb_bot.polling(none_stop=True, timeout=90, long_polling_timeout=60)
            backoff = 1
        except requests.exceptions.ReadTimeout:
            continue
        except requests.exceptions.ConnectionError as e:
            logger.error(f"[TELEGRAM] 连接错误 | error: {str(e)}")
        except Exception as e:
            logger.error(f"[TELEGRAM] 轮询异常 | error: {str(e)}")
        
        time.sleep(backoff)
        backoff = min(backoff * 2, 60)

def start_polling_thread():
    polling_thread = threading.Thread(target=start_telegram_polling, daemon=True)
    polling_thread.start()
