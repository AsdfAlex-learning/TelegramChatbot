from src.core.component_system.base import BaseComponent
import logging

class ExamplePingPongComponent(BaseComponent):
    """
    示例组件：Ping-Pong
    监听 Telegram 消息，如果收到 "ping"，回复 "pong from component"。
    """
    def on_enable(self):
        self.logger.info("PingPong 组件已启用！")
        
        # 获取 TeleBot 实例
        bot = self.context.bot
        
        # 注册消息处理器
        # 注意：这里我们使用 bot.register_message_handler 而不是装饰器
        # 因为在组件类内部装饰器处理 `self` 会比较麻烦，直接注册更清晰
        bot.register_message_handler(self.handle_ping, func=lambda m: m.text and m.text.lower() == "ping")

    def handle_ping(self, message):
        """处理 ping 消息"""
        self.logger.info(f"收到 Ping，来自 {message.from_user.id}")
        self.context.bot.reply_to(message, "🏓 Pong! (来自组件系统)")

    def on_disable(self):
        self.logger.info("PingPong 组件已禁用。")
