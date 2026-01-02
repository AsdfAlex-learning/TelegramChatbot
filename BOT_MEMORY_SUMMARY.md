# bot.py 与 memory.py 归纳总结（函数功能与执行流程）

本文档针对项目中的 [bot.py](file:///d:/Whoami/Nonebot/Telegram_Chatbot/bot.py) 与 [memory.py](file:///d:/Whoami/Nonebot/Telegram_Chatbot/memory.py) 做归纳总结，重点说明每个函数/方法的职责、关键输入输出，以及整体执行流程与调用链。

> 说明：你提到的 `boy.py`，在当前代码库中对应文件名为 `bot.py`。

## 总体结构

- **入口与运行框架**：`bot.py` 使用 NoneBot 作为启动器（`nonebot.run()`），并在启动时另起线程运行 `telebot` 的轮询（`tb_bot.polling(...)`）。
- **对话状态（按用户隔离）**：`deepseek_chat_active` 是一个 `set`，记录开启 AI 模式的用户 `user_id`。
- **短期上下文（按用户隔离）**：`chat_context[user_id]` 维护 DeepSeek `messages` 列表（system/user/assistant），长度被限制在 1 条 system + 最近 10 轮问答。
- **长期记忆（按用户隔离）**：`LongTermMemory(user_id)` 对应一个用户一个 SQLite 数据库文件，路径在 `memory.py` 的 `user_memories/` 目录下。
- **消息缓冲（按用户隔离）**：对普通聊天消息先缓冲并合并（15–20 秒窗口），再统一调用 AI 生成回复。

## 全局状态与锁（bot.py）

- `deepseek_chat_active: set[int]`：开启 AI 模式的用户集合。
- `chat_context: dict[int, list[dict]]`：每个用户的对话上下文（DeepSeek messages）。
- `user_message_count: dict[int, int]`：每个用户当前对话轮数计数，用于触发记忆更新。
- `user_prompt_cache: dict[int, tuple[str, float]]`：每个用户的 USER_PROMPT 与缓存时间（秒）。
- `user_message_buffer: dict[int, list[str]]`：每个用户的消息缓冲列表（用于合并多条消息）。
- `user_timers: dict[int, threading.Timer]`：每个用户的合并窗口定时器。
- `chat_lock / context_lock / buffer_lock / memory_lock`：分别保护开关集合、上下文、缓冲与计时器、记忆实例缓存的并发访问。

## 执行流程（从启动到回复）

### 1) 启动阶段

1. 运行 `python bot.py` 进入 `if __name__ == "__main__": nonebot.run()`。
2. NoneBot 初始化（`nonebot.init(env_file=".env.prod")`）并创建 `driver`。
3. 在 `@driver.on_startup` 标记的 `startup()` 中：
   - 创建守护线程执行 `start_telegram_polling()`；
   - `start_telegram_polling()` 内部调用 `tb_bot.polling(...)` 开始长轮询接收 Telegram 消息。

### 2) Telegram 消息分发（telebot）

`telebot` 收到消息后，会按 `@tb_bot.message_handler(...)` 规则分发到对应处理函数：

- `/start_aiGF` → `handle_start_deepseek`
- `/stop_aiGF` → `handle_stop_deepseek`
- 其他文本消息 → `handle_deepseek_chat`

### 3) 开启 AI 模式：/start_aiGF

`handle_start_deepseek(message)` 做以下事情：

1. 取 `user_id = message.from_user.id`。
2. 加锁后把 `user_id` 加入 `deepseek_chat_active`（允许该用户进入 AI 模式）。
3. 初始化长期记忆实例：`get_user_memory(user_id)`（懒加载创建 SQLite DB）。
4. 生成初始 USER_PROMPT：`generate_user_prompt(user_id)`（带 24h 缓存）。
5. 重置该用户对话计数：`user_message_count[user_id] = 0`。
6. 回复提示文本（已开启）。

### 4) 关闭 AI 模式：/stop_aiGF

`handle_stop_deepseek(message)` 做以下事情：

1. 加锁后把 `user_id` 从 `deepseek_chat_active` 移除（该用户后续消息不再触发 AI）。
2. 清理短期数据（缓冲区、计时器、计数）。
3. 清理对话上下文 `chat_context[user_id]` 与 USER_PROMPT 缓存 `user_prompt_cache[user_id]`。
4. 回复提示文本（已关闭）。

### 5) 普通聊天消息：缓冲 → 合并 → AI → 发送

#### 5.1 入口：handle_deepseek_chat

`handle_deepseek_chat(message)`：

1. 忽略 `/start_aiGF`、`/stop_aiGF`（避免重复处理）。
2. 获取 `user_id`，检查 `user_id in deepseek_chat_active`；不在则直接返回。
3. 取 `user_input = message.text.strip()`；为空则提示后返回。
4. 调用 `add_user_message(user_id, user_input)` 将消息加入缓冲并启动/重置定时器。

#### 5.2 缓冲合并：add_user_message

`add_user_message(user_id, message_text)`：

1. 将 `message_text` 追加到 `user_message_buffer[user_id]`。
2. 随机生成一个合并窗口 `collect_time ∈ [15, 20]`。
3. 若该用户已有未触发的计时器，则 `cancel()` 旧计时器。
4. 启动新计时器：到期调用 `process_user_messages(user_id)`。

#### 5.3 统一处理：process_user_messages

`process_user_messages(user_id)`（核心流水线）：

1. 从缓冲区取出并合并消息：`packed_message = "\n".join(buffer)`，然后清空缓冲。
2. 增加对话轮数计数 `user_message_count[user_id] += 1`，用于决定何时更新长期记忆。
3. 关键词提取：`keywords = extract_keywords(packed_message)`。
4. 记忆匹配：`matched_memories = get_user_memory(user_id).match_keywords(keywords)`。
   - 若匹配到，取第一条记忆事件作为 `extra_context`，用于“提醒”模型。
5. 调用 AI：`deepseek_reply = call_deepseek_api(user_id, packed_message, extra_context)`。
6. 记忆更新触发判断：
   - 在 8–12 轮之间，并且满足随机条件；或命中高重要关键词集合（如“生病/离职/生日 …”）。
7. 若触发更新：`new_memories = extract_new_memories(user_id)`，成功解析后调用 `memory.update_memories(new_memories)` 写入 SQLite 并导出 CSV。
8. 回复拆分与发送：
   - 按 `$` 分段；每段根据长度做模拟打字延时；
   - `tb_bot.send_message(user_id, segment)` 逐段发送。

## bot.py：函数清单（功能与关键点）

### 配置加载

- `load_secrets() -> dict`
  - 读取 `config/PROTECTED_INFO.json`，返回包含 `TELEGRAM_TOKEN/DEEPSEEK_API_KEY/DEEPSEEK_API_URL` 的字典。
- `load_personality_setting() -> str`
  - 读取 `config/Personality_Setting.json` 的 `system_prompt` 字段，作为基础系统提示词 `BASE_SYSTEM_PROMPT`。

### 长期记忆实例管理

- `get_user_memory(user_id) -> LongTermMemory`
  - 从 `user_memories` 缓存中获取该用户的 `LongTermMemory` 实例，不存在则创建并缓存。

### DeepSeek 调用与提示词构建

- `call_deepseek_api(user_id: int, prompt: str, extra_context: str = "") -> str`
  - 确保 `chat_context[user_id]` 初始化为 system 提示（`BASE_SYSTEM_PROMPT + USER_PROMPT`）。
  - 如果有 `extra_context`，额外追加一条 system 消息“相关记忆：...”（用于注入检索到的记忆）。
  - 追加用户消息后发起 HTTP 请求，并把 assistant 回复写回上下文。
  - 返回 assistant 文本；网络/字段异常则返回错误字符串。
- `generate_user_prompt(user_id) -> str`
  - 从 `LongTermMemory.load_valid_memories()` 取有效记忆，拼成描述文本，调用 DeepSeek 生成 ≤200 字的 USER_PROMPT。
  - 结果缓存 24 小时（`user_prompt_cache`）。

### 信息抽取（用于记忆匹配与写入）

- `extract_keywords(text) -> list[str]`
  - 调用 DeepSeek 抽取 ≤5 个关键词（逗号分隔）。
  - 异常时退化为 `text.split()[:5]`。
- `extract_new_memories(user_id) -> list[tuple[str, str, int, int]]`
  - 取该用户最近 20 条上下文（约 10 轮），拼成对话文本。
  - 调用 DeepSeek 按行输出：`事件,关键词,重要度,有效期`，逐行解析成元组列表返回。

### 缓冲、打包与发送

- `add_user_message(user_id, message_text) -> None`
  - 把消息加入缓冲，并启动/重置该用户的 `threading.Timer`。
- `process_user_messages(user_id) -> None`
  - 将缓冲消息打包合并；
  - 提取关键词→匹配记忆→调用 AI→（可选）更新长期记忆→拆分回复→分段发送。

### Telegram 处理器与轮询

- `handle_start_deepseek(message) -> None`
  - 将用户加入 AI 模式集合，并初始化记忆与 USER_PROMPT，重置计数。
- `handle_stop_deepseek(message) -> None`
  - 将用户移出 AI 模式集合，并清理缓冲/计时器/上下文/缓存。
- `handle_deepseek_chat(message) -> None`
  - 若用户未开启 AI 模式则忽略；否则将消息加入缓冲等待合并处理。
- `start_telegram_polling() -> None`
  - 启动 `tb_bot.polling(...)`，并打印可用命令。
- `startup() -> None`
  - NoneBot 启动钩子：创建线程运行 `start_telegram_polling()`。

## memory.py：数据结构与方法清单

### 存储结构

- 目录：`memory.py` 启动时确保存在 `user_memories/` 目录。
- 每个用户一个 SQLite：`user_memories/user_{user_id}.db`
- 备份 CSV：`user_memories/user_{user_id}_backup.csv`
- 表结构 `memories`：
  - `id`：自增主键
  - `event`：事件文本（约定含日期）
  - `keywords`：关键词字符串（逗号分隔）
  - `importance`：重要度（0–100）
  - `create_time`：创建时间（默认当前时间）
  - `expiry_days`：有效期天数（365 表示长期）
  - `last_mentioned`：最近被提及时间（用于衰减策略）

### LongTermMemory 方法

- `__init__(user_id)`
  - 计算该用户 DB/CSV 路径；创建锁；调用 `init_database()` 确保表存在。
- `init_database()`
  - 创建 `memories` 表（不存在则创建）。
- `load_valid_memories() -> list[tuple]`
  - 读取“有效记忆”：`importance >= 30`，且未过期（或 `expiry_days = 365` 永久）。
- `match_keywords(input_keywords, max_matches=2) -> list[tuple]`
  - 从 `importance >= 50` 的记忆中做包含匹配：任一 `input_keywords` 子串命中 `keywords` 字段即认为匹配。
  - 最多返回 `max_matches` 条。
- `update_last_mentioned(memory_id) -> None`
  - 更新某条记忆的 `last_mentioned = CURRENT_TIMESTAMP`。
- `update_memories(new_memories) -> None`
  - 对全部记忆做重要度衰减（7 天内提及过衰减慢，否则衰减快）。
  - 插入新记忆并做“事件去重”（按 `event.split(' ')[1]` 的片段做 LIKE 匹配；新重要度更高则删除旧条目）。
  - 清理低价值或过期记忆。
  - 调用 `sync_to_csv()` 导出 CSV。
- `sync_to_csv() -> None`
  - 将 `memories` 全量导出到 CSV 文件，作为备份。

