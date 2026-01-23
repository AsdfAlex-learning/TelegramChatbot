from src.bot.telegram.client import tb_bot
from src.bot.wiring import bot_app
from src.core.logger import get_logger

# =============================================================================
# [Telegram Handlers] IO 适配层
# 职责：负责将 Telegram 的事件（Message）转换为 App 能理解的调用。
# 规则：
# 1. 它是 Telegram 和 App 之间的“翻译官”。
# 2. 它只做三件事：提取参数 -> 调用 App -> 发送结果。
# 3. 不包含任何复杂的业务判断（如权限检查、状态管理），这些都交给 App。
# =============================================================================

logger = get_logger("TelegramHandlers")

# Review Note: 这里直接导入了 bot_app (来自 wiring) 和 tb_bot (来自 client)。
# 这是一种“Service Locator”模式的变体，虽然简单，但导致 handlers 强耦合于 wiring。
# 在更严格的架构中，handlers 应该通过 setup(bot, app) 函数动态注册，而不是依赖全局变量。

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
    # 过滤命令（防止命令被当成普通对话处理）
    if message.text.strip().startswith(('/start_aiGF', '/stop_aiGF', '/help')):
        return
    
    user_id = message.from_user.id
    user_input = message.text.strip()
    
    # 调用 App 处理
    response = bot_app.handle_user_message(user_id, user_input)
    
    # 如果有同步返回的消息（例如错误提示），则发送
    if response:
        tb_bot.reply_to(message, response)
