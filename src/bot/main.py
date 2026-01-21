import nonebot
import os
import threading
import telebot
import requests
import time
from nonebot import get_driver
from src.core.config_loader import ConfigLoader
from src.bot.proactive_messaging import ProactiveScheduler
from src.core.chat_service import ChatService
from src.core.interaction import InteractionManager
from src.core.proactive_service import ProactiveService
from src.core.session_controller import SessionController
from src.core.logger import get_logger

# 初始化日志
logger = get_logger("TelegramBot")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

nonebot.init(env_file=os.path.join(PROJECT_ROOT, ".env.prod"))
driver = get_driver()

config_loader = ConfigLoader()
system_config = config_loader.system_config

session_controller = SessionController(
    owner_id=system_config.telegram.owner_id,
    private_mode_default=system_config.bot.private_mode_default
)

chat_service = ChatService(session_controller)
interaction_manager = InteractionManager(chat_service, session_controller)
proactive_service = ProactiveService(session_controller, chat_service)

TELEGRAM_TOKEN = system_config.telegram.bot_token
OWNER_ID = system_config.telegram.owner_id

# 初始化Telegram机器人
tb_bot = telebot.TeleBot(TELEGRAM_TOKEN)

def safe_send_message(chat_id, text, max_attempts=3):
    backoff = 1
    for attempt in range(max_attempts):
        try:
            tb_bot.send_message(chat_id, text)
            return True
        except requests.exceptions.RequestException as e:
            if attempt == max_attempts - 1:
                logger.error(f"[TELEGRAM] SEND_FAIL | chat_id: {chat_id} | error: {e}")
                return False
            time.sleep(backoff)
            backoff = min(backoff * 2, 10)
        except Exception as e:
            logger.error(f"[TELEGRAM] SEND_ERROR | chat_id: {chat_id} | error: {e}")
            return False

# Register sender
interaction_manager.set_sender(lambda uid, txt: safe_send_message(uid, txt))

# 初始化主动消息调度器
proactive_scheduler = ProactiveScheduler(
    proactive_service=proactive_service,
    chat_service=chat_service,
    sender=lambda uid, txt: safe_send_message(uid, txt)
)


# ====================== Telegram消息处理器 ======================
@tb_bot.message_handler(func=lambda msg: msg.text.strip() == "/help")
def handle_help(message):
    help_text = (
        "📖 可用命令：\n"
        "/start_aiGF - 开启ai女友对话模式\n"
        "/stop_aiGF - 关闭ai女友对话模式\n"
        "/help - 显示此帮助信息"
    )
    tb_bot.reply_to(message, help_text)
    logger.info(f"[TELEGRAM] HELP_REQUEST | user_id: {message.from_user.id}")


@tb_bot.message_handler(func=lambda msg: msg.text.strip() == "/start_aiGF")
def handle_start_ai_chat(message):
    user_id = message.from_user.id
    
    if not session_controller.start_session(user_id):
        tb_bot.reply_to(message, "🔒 机器人当前处于私有模式，仅管理员可用。")
        return
        
    chat_service.start_chat(user_id)
    
    # 启动主动消息循环
    proactive_scheduler.start(user_id)

    tb_bot.reply_to(message, "✅ ai女友对话已开启！现在可以直接发送消息获取回复，输入/stop_aiGF关闭该模式。")
    logger.info(f"[TELEGRAM] SESSION_START | user_id: {user_id}")

@tb_bot.message_handler(func=lambda msg: msg.text.strip() == "/stop_aiGF")
def handle_stop_ai_chat(message):
    user_id = message.from_user.id
    
    chat_service.stop_chat(user_id)
    session_controller.stop_session(user_id)
    interaction_manager.clear_user_state(user_id)
    
    # 停止主动消息循环
    proactive_scheduler.stop(user_id)

    tb_bot.reply_to(message, "❌ ai女友对话模式已关闭！")
    logger.info(f"[TELEGRAM] SESSION_STOP | user_id: {user_id}")

@tb_bot.message_handler(func=lambda msg: True)
def handle_ai_chat(message):
    if message.text.strip().startswith(('/start_aiGF', '/stop_aiGF', '/help')):
        return
    
    user_id = message.from_user.id
    user_input = message.text.strip()
    
    # telegram无法发送空白消息 所以好像有没有无所谓
    if not user_input:
        tb_bot.reply_to(message, "⚠️ 消息内容不能为空，请重新输入！")
        return
    
    # 用户活跃，重置主动消息计时器
    proactive_scheduler.on_user_activity(user_id)

    interaction_manager.add_user_message(user_id, user_input)

# ====================== Telegram轮询线程 ======================
def start_telegram_polling():
    logger.info("[TELEGRAM] POLLING_START")
    backoff = 1
    while True:
        try:
            tb_bot.polling(none_stop=True, timeout=90, long_polling_timeout=60)
            backoff = 1
        except requests.exceptions.ReadTimeout:
            continue
        except requests.exceptions.ConnectionError as e:
            logger.error(f"[TELEGRAM] POLLING_CONN_ERROR | error: {str(e)}")
        except Exception as e:
            logger.error(f"[TELEGRAM] POLLING_ERROR | error: {str(e)}")
        time.sleep(backoff)
        backoff = min(backoff * 2, 60)

# ====================== NoneBot启动配置 ======================
@driver.on_startup
async def startup():
    polling_thread = threading.Thread(target=start_telegram_polling, daemon=True)
    polling_thread.start()

# ====================== 运行NoneBot ======================
if __name__ == "__main__":
    nonebot.run()
