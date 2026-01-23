import os
import nonebot
from nonebot import get_driver
from src.core.config_loader import ConfigLoader
from src.core.session_controller import SessionController
from src.core.chat_service import ChatService
from src.core.interaction import InteractionManager
from src.core.proactive_service import ProactiveService
from src.bot.proactive_messaging import ProactiveScheduler
from src.core.component_system.base import ComponentContext
from src.core.component_system.loader import ComponentLoader
from src.core.logger import get_logger

# =============================================================================
# [Wiring] 依赖组装层
# 职责：负责所有核心对象的实例化、依赖注入和组装。
# 地位：这是应用程序的“组合根”(Composition Root)。
# 规则：
# 1. 它是唯一知道所有 Service/Controller 存在的模块。
# 2. 它不应该包含任何业务逻辑（if/else）。
# 3. 它不属于 Telegram，也不属于业务核心，它只是“胶水”。
# =============================================================================

logger = get_logger("Wiring")

# 1. 加载配置
# Review Note: 这里使用了 ConfigLoader，它会读取环境变量和配置文件。
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
nonebot.init(env_file=os.path.join(PROJECT_ROOT, ".env.prod"))
driver = get_driver()

config_loader = ConfigLoader()
system_config = config_loader.system_config

# 2. 初始化核心服务 (Core Services)
# Review Note: SessionController 是会话管理的唯一事实来源，需要被注入到其他服务中。
session_controller = SessionController(
    owner_id=system_config.telegram.owner_id,
    private_mode_default=system_config.bot.private_mode_default
)

chat_service = ChatService(session_controller)
proactive_service = ProactiveService(session_controller, chat_service)

# 3. 初始化交互与主动消息 (Interaction & Proactive)
# Review Note: 这里存在一个循环依赖问题 —— InteractionManager 需要发送消息 (Sender)，
# 但发送消息的 Client (Telegram) 同时也需要依赖 wiring 来启动。
# 解决方案：使用 lambda 延迟绑定 sender，或者在下方导入 client。
# 这里我们采用“延迟导入 + Lambda 注入”的方式来解耦。

# 延迟导入，防止循环引用 (Circular Import)
from src.bot.telegram.client import safe_send_message, tb_bot

interaction_manager = InteractionManager(chat_service, session_controller)
# 注入发送函数：InteractionManager 不需要知道 Telegram 的存在，只需要一个 Callable
interaction_manager.set_sender(lambda uid, txt: safe_send_message(uid, txt))

proactive_scheduler = ProactiveScheduler(
    proactive_service=proactive_service,
    chat_service=chat_service,
    # 注入发送函数
    sender=lambda uid, txt: safe_send_message(uid, txt)
)

# 4. 组件系统 (Component System)
# Review Note: 组件系统需要访问所有核心服务，以便让插件能够操作 Bot。
component_context = ComponentContext(
    bot=tb_bot,
    session_controller=session_controller,
    chat_service=chat_service,
    interaction_manager=interaction_manager
)
component_loader = ComponentLoader(component_context)
component_loader.load_all_components()

# 5. 初始化应用外观 (Application Facade)
# Review Note: BotApplication 是对外的统一入口，它封装了所有内部服务的调用。
from src.bot.app import BotApplication
bot_app = BotApplication(
    session_controller=session_controller,
    chat_service=chat_service,
    interaction_manager=interaction_manager,
    proactive_scheduler=proactive_scheduler
)
