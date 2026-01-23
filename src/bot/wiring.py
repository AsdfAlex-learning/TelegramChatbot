import os
from src.core.config_loader import ConfigLoader
from src.core.session_controller import SessionController
from src.core.chat_service import ChatService
from src.core.interaction import InteractionManager
from src.core.proactive_service import ProactiveService
from src.bot.proactive_messaging import ProactiveScheduler
from src.core.component_system.base import ComponentContext
from src.core.component_system.loader import ComponentLoader
from src.core.logger import get_logger

logger = get_logger("Wiring")

# 1. 加载配置
config_loader = ConfigLoader()
system_config = config_loader.system_config

# 2. 初始化核心服务
session_controller = SessionController(
    owner_id=system_config.telegram.owner_id,
    private_mode_default=system_config.bot.private_mode_default
)

chat_service = ChatService(session_controller)
proactive_service = ProactiveService(session_controller, chat_service)

# 3. 初始化交互与主动消息
# 延迟导入以避免循环依赖
from src.bot.telegram.client import safe_send_message, tb_bot

interaction_manager = InteractionManager(chat_service, session_controller)
# 注入发送函数
interaction_manager.set_sender(lambda uid, txt: safe_send_message(uid, txt))

proactive_scheduler = ProactiveScheduler(
    proactive_service=proactive_service,
    chat_service=chat_service,
    sender=lambda uid, txt: safe_send_message(uid, txt)
)

# 4. 组件系统
component_context = ComponentContext(
    bot=tb_bot,
    session_controller=session_controller,
    chat_service=chat_service,
    interaction_manager=interaction_manager
)
component_loader = ComponentLoader(component_context)
component_loader.load_all_components()

# 5. 初始化应用外观
from src.bot.app import BotApplication
bot_app = BotApplication(
    session_controller=session_controller,
    chat_service=chat_service,
    interaction_manager=interaction_manager,
    proactive_scheduler=proactive_scheduler
)
