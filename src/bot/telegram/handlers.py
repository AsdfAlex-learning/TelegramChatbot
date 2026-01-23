from src.bot.telegram.client import tb_bot
from src.bot.wiring import bot_app
from src.core.logger import get_logger

logger = get_logger("TelegramHandlers")

@tb_bot.message_handler(func=lambda msg: msg.text.strip() == "/help")
def handle_help(message):
    logger.info(f"[TELEGRAM] 收到帮助请求 | user_id: {message.from_user.id}")
    response = bot_app.get_help_text()
    tb_bot.reply_to(message, response)

@tb_bot.message_handler(func=lambda msg: msg.text.strip() == "/start_aiGF")
def handle_start_ai_chat(message):
    user_id = message.from_user.id
    response = bot_app.start_ai_session(user_id)
    tb_bot.reply_to(message, response)

@tb_bot.message_handler(func=lambda msg: msg.text.strip() == "/stop_aiGF")
def handle_stop_ai_chat(message):
    user_id = message.from_user.id
    response = bot_app.stop_ai_session(user_id)
    tb_bot.reply_to(message, response)

@tb_bot.message_handler(func=lambda msg: True)
def handle_ai_chat(message):
    # 过滤命令
    if message.text.strip().startswith(('/start_aiGF', '/stop_aiGF', '/help')):
        return
    
    user_id = message.from_user.id
    user_input = message.text.strip()
    
    # 调用 App 处理
    response = bot_app.handle_user_message(user_id, user_input)
    
    if response:
        tb_bot.reply_to(message, response)
