from src.core.logger import get_logger
from src.core.session_controller import SessionController
from src.core.chat_service import ChatService
from src.core.interaction import InteractionManager
from src.bot.proactive_messaging import ProactiveScheduler

# =============================================================================
# [BotApplication] 业务编排层
# 职责：作为业务逻辑的统一入口，协调各个 Service 工作。
# 规则：
# 1. 绝对不可以 import telebot！它必须不知道 Telegram 的存在。
# 2. 只处理纯数据（int user_id, str input），不处理 Message 对象。
# 3. 负责“要做什么”（调用 ChatService），不负责“怎么做”（IO 细节）。
# =============================================================================

logger = get_logger("BotApplication")

class BotApplication:
    def __init__(self, 
                 session_controller: SessionController,
                 chat_service: ChatService,
                 interaction_manager: InteractionManager,
                 proactive_scheduler: ProactiveScheduler):
        self.session_controller = session_controller
        self.chat_service = chat_service
        self.interaction_manager = interaction_manager
        self.proactive_scheduler = proactive_scheduler

    def get_help_text(self) -> str:
        return (
            "📖 可用命令：\n"
            "/start_aiGF - 开启ai女友对话模式\n"
            "/stop_aiGF - 关闭ai女友对话模式\n"
            "/help - 显示此帮助信息"
        )

    def start_ai_session(self, user_id: int) -> str:
        """开启 AI 会话"""
        if not self.session_controller.start_session(user_id):
            return "🔒 机器人当前处于私有模式，仅管理员可用。"
        
        self.chat_service.start_chat(user_id)
        self.proactive_scheduler.start(user_id)
        
        logger.info(f"[APP] 会话开启 | user_id: {user_id}")
        return "✅ ai女友对话已开启！现在可以直接发送消息获取回复，输入/stop_aiGF关闭该模式。"

    def stop_ai_session(self, user_id: int) -> str:
        """关闭 AI 会话"""
        self.chat_service.stop_chat(user_id)
        self.session_controller.stop_session(user_id)
        self.interaction_manager.clear_user_state(user_id)
        self.proactive_scheduler.stop(user_id)
        
        logger.info(f"[APP] 会话结束 | user_id: {user_id}")
        return "❌ ai女友对话模式已关闭！"

    def handle_user_message(self, user_id: int, user_input: str) -> str:
        """处理用户消息"""
        if not user_input:
            return "⚠️ 消息内容不能为空，请重新输入！"

        # 用户活跃，重置主动消息计时器
        self.proactive_scheduler.on_user_activity(user_id)

        # 添加到交互管理器进行处理
        # 注意：interaction_manager 会异步/缓冲处理，这里可能不直接返回回复
        # Review Note: 这里的 None 返回值表明没有同步回复。
        # 实际的回复会通过 InteractionManager 注入的 sender (safe_send_message) 异步发送。
        self.interaction_manager.add_user_message(user_id, user_input)
        return None  # 无直接同步回复
