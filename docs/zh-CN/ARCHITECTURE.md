# 系统架构设计 (System Architecture)

本文档描述了本项目的核心架构设计，采用 **Kernel-Satellite (核心-卫星)** 模式，旨在构建一个可长期演进、支持多端接入（Telegram, Live2D 等）的 AI 陪伴系统。

## 1. 核心理念 (Core Philosophy)

*   **Single Source of Truth (SSOT)**: 所有的状态（会话、记忆、上下文）由 Core 统一管理，外部模块只读或通过受控接口写入。
*   **Kernel-Satellite Pattern**: 
    *   **Kernel (Core)**: 负责业务逻辑、LLM 交互、状态管理、记忆维护。
    *   **Satellite (Clients)**: 负责 I/O、渲染、平台特定适配 (Telegram Bot, Live2D Unity)。
*   **Thin Client, Fat Core**: 客户端应尽可能轻量，只负责展示和转发用户意图；复杂的决策和生成逻辑全部在 Core 完成。

## 2. 模块职责 (Module Responsibilities)

### 2.1 Core (Kernel) - `src/core/`

Core 是系统的“大脑”，不依赖于任何特定的 I/O 平台。

| 模块文件 | 职责说明 | 关键功能 |
| :--- | :--- | :--- |
| `session_controller.py` | **会话控制器**。权限管理的 SSOT，管理谁在聊、谁能聊。 | 启动/停止会话，私有模式检查，并发锁。 |
| `chat_service.py` | **聊天服务**。核心业务编排者。 | 接收输入 -> 组装 Prompt -> LLM -> 更新上下文 -> 触发记忆。 |
| `interaction.py` | **交互管理器**。负责“像人一样说话”的节奏。 | 消息缓冲 (防刷屏)，打字机效果 (Chunk 发送)，错误反馈。 |
| `proactive_service.py` | **主动消息服务**。负责“主动发起”的决策与生成。 | 策略判断 (是否发)，内容生成 (发什么)。不含定时器。 |
| `context.py` | **上下文模型**。短期记忆的数据结构。 | 维护最近 N 条对话，生成 Prompt 用的摘要。 |
| `context_snapshot.py` | **快照服务**。对外同步状态的标准接口。 | 生成只读的 `ContextSnapshot`，供 Live2D 等外部读取。 |
| `memory_ingest.py` | **记忆注入**。长期记忆的写入标准。 | 定义 `MemoryPayload`，确保只有结构化总结能进入数据库。 |
| `summary_contract.py` | **总结契约**。定义何时触发记忆总结。 | `SummaryHint` (触发信号) 和 `ISummaryTriggerPolicy` (触发策略)。 |
| `config_loader.py` | **配置中心**。单例配置加载。 | 加载 system, ai_rules, persona 等 YAML 配置。 |

### 2.2 Bot (Satellite) - `src/bot/`

Bot 是 Telegram 平台的适配层，负责轮询消息和调度定时任务。

| 模块文件 | 职责说明 |
| :--- | :--- |
| `main.py` | **入口与装配**。初始化 Core 组件，注入依赖，启动 Telegram 轮询。 |
| `proactive_messaging.py` | **调度器 (Scheduler)**。负责定时任务和 IO 调用，**不包含**内容决策逻辑。 |

## 3. 关键数据流 (Data Flow)

### 3.1 消息处理流程 (Telegram -> Core -> Telegram)

1.  **User Input**: 用户在 Telegram 发送消息。
2.  **Bot Layer**: `main.py` 收到消息，调用 `interaction_manager.add_user_message`。
3.  **Buffering**: `InteractionManager` 缓冲消息（防多条连发），随机延迟后触发处理。
4.  **Core Processing**:
    *   `ChatService` 获取 `ConversationContext`。
    *   `ChatService` 从 `LongTermMemory` 获取相关记忆。
    *   `PromptManager` 组装 System Prompt + Persona + Memory + Context。
    *   `LLMClient` 调用 API 获取回复。
5.  **State Update**:
    *   回复被追加到 Context。
    *   （异步）触发记忆总结检查。
6.  **Response Delivery**: `InteractionManager` 将回复切片，模拟打字节奏，通过回调函数调用 Telegram API 发送。

### 3.2 主动消息流程 (Timer -> Core -> Telegram)

1.  **Timer Trigger**: `ProactiveScheduler` (Bot层) 定时器触发。
2.  **Policy Check**: 调度器调用 `ProactiveService.should_trigger` (Core层)。
3.  **Decision**: Core 检查当前会话状态、概率等，决定是否发送。
4.  **Generation**: 如果通过，Core 调用 LLM 生成一句“开场白”。
5.  **Execution**: Core 返回内容，调度器调用 `sender` 发送消息。

### 3.3 外部同步流程 (Live2D <-> Core)

*   **Read (Poll)**: Live2D 客户端定期请求 `SnapshotService.generate_snapshot(user_id)`，获取当前的表情、心情、对话进度。
*   **Write (Request)**: Live2D 客户端不直接写库，而是发送 `SummaryHint` 请求 Core 进行总结，或发送 `MemoryPayload` 请求 Core 注入记忆（需鉴权）。

## 4. 目录结构 (Directory Structure)

```text
src/
├── api/                # 外部工具集成 (天气等)
├── bot/                # Telegram 机器人适配层 (Controller / View)
│   ├── main.py         # 程序入口
│   └── proactive_messaging.py # 定时调度器
├── core/               # 核心业务逻辑 (Model / Service)
│   ├── chat_service.py # 核心业务流
│   ├── context.py      # 上下文数据
│   ├── interaction.py  # 交互节奏管理
│   ├── memory_ingest.py# 记忆注入接口
│   └── ...
├── storage/            # 数据存储层
└── ...
```

## 5. 设计原则总结

1.  **依赖倒置**: Bot 依赖 Core，Core 不依赖 Bot。Core 通过回调接口 (Callback) 或抽象接口 (Interface) 与外部交互。
2.  **读写分离**: 外部系统（Live2D）对核心状态通常是“只读快照”，写入必须通过特定服务接口。
3.  **关注点分离**:
    *   `InteractionManager`: 关注“怎么发”（节奏、分段）。
    *   `ChatService`: 关注“发什么”（内容、逻辑）。
    *   `ProactiveService`: 关注“什么时候主动发”。
4.  **防御性编程**: Core 层对输入（如记忆注入）进行严格校验，防止外部污染核心数据。
