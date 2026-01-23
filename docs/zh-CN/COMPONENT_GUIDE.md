# 组件系统开发指南

本项目支持一种轻量级的组件系统，允许通过编写单个 `.py` 文件来扩展机器人功能（类似于 Minecraft 的 Mods/Plugins）。

## 1. 组件系统原理

- **目录**: 所有的组件文件都应该放在 `src/components/` 目录下。
- **自动加载**: 机器人启动时，`ComponentLoader` 会自动扫描该目录下所有的 `.py` 文件。
- **基类**: 每个组件必须继承自 `BaseComponent` 类。
- **生命周期**: 系统会自动调用 `on_enable()` 进行初始化，在关闭时调用 `on_disable()`。

## 2. 如何编写一个组件

### 步骤 1: 创建文件
在 `src/components/` 下创建一个新的 Python 文件，例如 `my_feature.py`。

### 步骤 2: 继承 `BaseComponent`
在文件中导入基类并实现你的逻辑。

```python
from src.core.component_system.base import BaseComponent

class MyFeatureComponent(BaseComponent):
    def on_enable(self):
        # 组件启动逻辑
        self.logger.info("组件已启动")
        
        # 注册 Telegram 消息监听
        # 这里的 self.context.bot 就是 TeleBot 实例
        self.context.bot.register_message_handler(
            self.handle_message, 
            func=lambda m: m.text == "hello"
        )

    def handle_message(self, message):
        self.context.bot.reply_to(message, "World!")

    def on_disable(self):
        # 清理逻辑
        self.logger.info("组件已关闭")
```

## 3. `ComponentContext` 提供的能力

`self.context` 提供了对核心系统的访问权限：

- `self.context.bot`: TeleBot 实例（用于发送消息、注册 Handler）。
- `self.context.session_controller`: 会话控制器（检查权限、管理会话）。
- `self.context.chat_service`: 聊天服务（用于更底层的 LLM 交互）。
- `self.context.interaction_manager`: 交互管理器（用于发送带缓冲/节奏控制的消息）。

## 4. 最佳实践

1. **单个类**: 一个文件建议只包含一个继承自 `BaseComponent` 的类。
2. **日志**: 使用 `self.logger` 进行日志记录，系统会自动带上组件名称。
3. **异常处理**: 即使组件崩溃，也不应影响主程序的运行，但请在组件内部做好异常捕获。
4. **命名**: 文件名和类名尽量具有描述性。
