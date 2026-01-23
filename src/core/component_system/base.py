from typing import Any, Dict
import logging

class ComponentContext:
    """
    组件上下文。
    包含组件运行所需的系统引用。
    """
    def __init__(self, 
                 bot: Any, 
                 session_controller: Any, 
                 chat_service: Any, 
                 interaction_manager: Any):
        self.bot = bot
        self.session_controller = session_controller
        self.chat_service = chat_service
        self.interaction_manager = interaction_manager

class BaseComponent:
    """
    所有组件的基类。
    用户编写的组件必须继承此类。
    """
    def __init__(self, context: ComponentContext):
        self.context = context
        self.logger = logging.getLogger(self.__class__.__name__)

    def on_enable(self):
        """
        当组件被加载并启用时调用。
        在此处注册事件监听、启动定时任务等。
        """
        pass

    def on_disable(self):
        """
        当组件被禁用或系统关闭时调用。
        在此处清理资源、取消监听等。
        """ 
        pass
