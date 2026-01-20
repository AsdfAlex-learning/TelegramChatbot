# 系统架构设计文档：多端协同与核心状态管理

> **文档状态**：Draft  
> **版本**：v1.0  
> **目标读者**：系统架构师、后端工程师、客户端开发者  

## 一、 系统设计总览

本系统采用 **"内核-卫星" (Kernel-Satellite)** 架构模式。

*   **核心系统 (Kernel)**：作为唯一的“大脑”和“记忆库”，负责维护所有状态（Context）、管理长期记忆（Memory）、执行认知任务（LLM Interaction）以及权限控制。它是**唯一的真理来源 (Single Source of Truth)**。
*   **交互端 (Satellites)**：Telegram Bot、Live2D Client 等均为“哑终端”或“富客户端”。它们负责表现层（UI/Animation）和输入采集，但不持有核心业务状态，也不直接操作底层数据。

这种设计确保了无论用户通过何种入口（文字/语音/Live2D）与 AI 交互，其**“人格连续性”**和**“记忆一致性”**都能得到严格保障。所有状态变更必须经过核心系统的业务逻辑层，杜绝了外部篡改和状态分裂的风险。

---

## 二、 Context Snapshot（上下文快照）设计

Context Snapshot 是核心系统向外部交互端暴露的**只读状态副本**。它用于解决多端协同中的“状态同步”问题，让 Live2D 等客户端能实时感知当前的对话进度、情感状态和短期历史，而无需直接访问核心内存。

### 1. 职责
*   **只读同步**：提供当前对话场景的完整状态，供客户端渲染 UI 或决定动画逻辑。
*   **状态解耦**：客户端依赖 Snapshot 数据结构，而不依赖核心系统的内部实现类。
*   **原子性**：每次请求返回的都是某一时刻的完整一致性视图。

### 2. 生命周期
*   **生成时机**：每次 Core 完成一轮对话交互（User Input -> LLM Response -> Context Updated）后，自动重新生成/更新缓存。但是，Snapshot 只能由 Core 内部的 ContextManager / SnapshotService 生成。Context Snapshot 由 Core 内部 SnapshotService 从 ContextManager 派生生成，任何外部模块不得自行构造或伪造 Snapshot。
*   **过期策略**：基于 Session 会话窗口，会话结束或超时后失效。

### 3. 数据结构 (伪代码/JSON Schema)

Snapshot 是可序列化的（JSON），方便通过 HTTP/WebSocket 传输。

```json
{
  "meta": {
    "snapshot_id": "uuid-v4",
    "timestamp": 1716280000,
    "version": "1.0"
  },
  "session": {
    "user_id": 12345,
    "active_session_id": "sess_abc123",
    "is_private_mode": true
  },
  "state": {
    "current_mood": "happy",          // 当前情感状态（由 LLM 分析或规则推断）
    "interaction_depth": 5,           // 当前会话轮次
    "last_active_component": "telegram" // 最后活跃的来源
  },
  "short_term_context": [             // 最近 N 条消息（用于客户端回显或上下文理解）
    {
      "role": "user",
      "content": "今天天气真好",
      "timestamp": 1716279990,
      "source": "live2d"
    },
    {
      "role": "assistant",
      "content": "是呀，要不要出去走走？",
      "timestamp": 1716280000,
      "mood_tag": "excited"
    }
  ]
}
```

### 4. 访问特性
*   **多 Client 支持**：支持多个客户端同时轮询或订阅。
*   **不可变性**：客户端接收到的对象是不可变的，任何修改尝试都不会影响核心系统。

---

## 三、 Memory Ingest（长期记忆注入接口）设计

为了保证记忆的纯净度和可解释性，长期记忆的写入必须通过严格受控的 `Ingest` 接口。此接口**不直接暴露给外部网络**，而是作为 Core 内部 **Summary Service** 的下游。

注意！！！Memory Ingest 不是对外 API Endpoint，而是 Core 内部受控调用路径，不暴露 HTTP 接口

### 1. 接口定义 (Python Abstract Base Class)

```python
from enum import Enum
from dataclasses import dataclass
from datetime import datetime

class MemorySource(Enum):
    TELEGRAM = "telegram"
    LIVE2D = "live2d"
    SYSTEM_EVENT = "system"

@dataclass
class MemoryPayload:
    summary_text: str           # LLM 生成的纯文本总结
    keywords: list[str]         # 提取的关键标签
    importance_score: float     # 重要性权重 (0.0 - 1.0)
    related_context_ids: list   # 关联的原始对话 ID (用于溯源)
    source_platform: MemorySource
    timestamp: datetime

class MemoryManager:
    def ingest_summary(self, user_id: int, payload: MemoryPayload) -> bool:
        """
        记忆注入的标准入口。
        
        执行逻辑：
        1. 校验 payload 合法性 (text 非空, score 范围正确)
        2. 执行去重检查 (Vector Search 相似度对比)
        3. 写入向量数据库 (Vector Store) 和 关系型数据库 (SQL)
        4. 触发记忆衰减/清理任务 (可选)
        """
        pass
```

### 2. 权限与约束
*   **调用方限制**：仅限 Core 系统内部的 `SummaryAgent` 或 `BackgroundWorker` 调用。
*   **外部项目限制**：Live2D **绝对禁止** 调用此接口。Live2D 只能请求“触发总结任务” (`trigger_summary`)，而不能直接上传总结文本。
    *   *原因*：防止客户端逻辑错误导致“伪造记忆”或污染记忆库。记忆的生成（LLM 总结）必须在 Core 的可信环境中执行。

---

## 四、 Live2D 项目边界说明

Live2D 项目被定义为 **“高交互性的表现层”**，它是一个消费者，而不是决策者。

### ✅ Live2D 能做的 (Capabilities)
1.  **用户输入**：采集语音或文本，发送给 Core 的 Chat API。
2.  **表现渲染**：从 Core 获取 `Context Snapshot`，根据 `current_mood` 播放对应的动作/表情。
3.  **被动查询**：查询历史记忆（通过 Core 提供的只读 API）以展示回顾页面。
4.  **请求任务**：Live2D 发出的仅是 Summary Hint，Core 会基于：session 状态，最近记忆密度，冷却时间，自行决定是否生成总结。

### ❌ Live2D 不能做的 (Restrictions)
1.  **私自决策**：不能自行决定 AI 回复什么内容（必须调用 Core Chat API）。
2.  **直接写库**：严禁直接连接 SQL/Vector DB。
3.  **持有状态**：不能在本地维护一套“私有上下文”，所有上下文必须同步自 Core。
4.  **调用 LLM**：严禁绕过 Core 直接调用 OpenAI/DeepSeek。所有的 Prompt 管理和 LLM 交互必须封装在 Core 内部。

### 💡 设计理由
*   **安全性**：防止 Client 端 Key 泄露。
*   **一致性**：避免 Live2D 和 Telegram 产生“人格分裂”（例如两边分别维护了不同的 Prompt 或记忆）。
*   **可维护性**：核心逻辑集中，Client 端代码轻量化，易于替换或升级。

---

再次补充重要内容
Core 内部通过 SessionController 统一管理：
- 会话生命周期
- Private Mode 权限
- 多 Client 访问一致性

## 五、 整体时序流程

### 流程 A：Telegram 文字聊天 → 形成长期记忆

1.  **User** 发送消息 "我今天领养了一只猫"。
2.  **Telegram Bot (Core)** 接收 Webhook，封装为 `Interaction` 对象。
3.  **InteractionManager** 缓冲消息，确认无后续输入。
4.  **ChatService**：
    *   加载 `Context` 和相关 `Memory`。
    *   组装 Prompt，调用 **LLM**。
    *   获得回复 "哇，恭喜！是什么品种的？"。
    *   **ContextManager** 更新短期上下文：`append(UserMsg, AiMsg)`。
5.  **InteractionManager** 将回复推送到 Telegram UI。
6.  **Async Scheduler (Core)** 检测到对话轮次达到阈值（或监测到“领养”等高权重意图）。
7.  **SummaryAgent (Core)**：
    *   读取最近 N 轮 Context。
    *   调用 **LLM** 生成总结："用户在 [日期] 领养了一只猫。"
    *   调用 **MemoryManager.ingest_summary(...)**。
8.  **MemoryManager** 将总结存入数据库。

### 流程 B：Live2D 聊天 → 同步上下文 → 触发总结 → 写入长期记忆

1.  **User** 在 Live2D 界面通过语音输入 "它是一只美短"。
2.  **Live2D Client** 将语音转文字，调用 Core API: `POST /api/chat {text: "它是一只美短"}`。
3.  **Core (ChatService)**：
    *   处理逻辑同上（加载 Context -> LLM -> Update Context）。
    *   返回响应 `{reply: "美短很可爱呢！取名字了吗？", mood: "curious"}`。
4.  **Live2D Client**：
    *   收到响应，播放 "Curious" 表情和 TTS 语音。
    *   (同时) 轮询或通过 WebSocket 收到新的 `Context Snapshot`，更新本地显示的对话历史。
5.  **User** 关闭 Live2D 窗口 / 结束会话。
6.  **Live2D Client** 调用 API: `POST /api/session/end` (或 Core 检测到超时)。
7.  **Core** 响应结束信号，标记 Session 结束。
8.  **SummaryAgent (Core)** 自动触发：
    *   分析该 Session 的 Context。
    *   生成总结："用户的猫是美短品种。"
    *   调用 **MemoryManager.ingest_summary(source=LIVE2D, ...)**。
9.  **MemoryManager** 存入数据库。

---

## 六、 设计原则总结

1.  **Single Source of Truth (SSOT)**：无论有多少个客户端，Context 和 Memory 永远只有一份，存在于 Core Database/Redis 中。
2.  **Unidirectional Data Flow (单向数据流)**：`Client -> Core -> LLM -> Core -> Client`。Client 永远不直接产生最终状态，只产生意图。
3.  **Thin Client, Fat Core (瘦客户端，胖内核)**：复杂的 Prompt 工程、记忆检索、情感分析全部在 Core 完成，Client 只负责“渲染”。
4.  **Explicit Interfaces (显式接口)**：模块间交互必须通过定义清晰的 API（Snapshot, Ingest），禁止“走后门”直接读写共享变量或数据库。
5.  **Asynchronous Persistence (异步持久化)**：记忆的总结和写入不应阻塞实时的对话交互流程。
