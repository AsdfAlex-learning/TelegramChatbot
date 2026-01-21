# 🧪 系统稳定性与调试清单 (Stability & Debug Checklist)

> **核心哲学**：训练自己，在系统出问题前，就知道它会怎么死。

本清单面向 **Kernel-Satellite (核心-卫星)** 架构设计，专注于有状态、异步 IO 及 LLM 驱动的系统稳定性。

---

## 一、 会话生命周期 (Session & Lifecycle)
**关联组件**：[session_controller.py](file:///d:/Whoami/Nonebot/Telegram_Chatbot/src/core/session_controller.py)
**稳定性目标**：确保权限隔离与资源清理的彻底性。

### ✅ 检查点
- [ ] **私有模式切换**：当 `private_mode` 开启时，所有非 Owner 的活跃会话是否被即时中断？
- [ ] **会话终止清理**：执行 `/stop` 后，是否同时清理了：
    - [ ] 内存中的短期上下文 (ContextManager)
    - [ ] 挂起的交互计时器 (InteractionManager)
    - [ ] 挂起的主动消息检查 (ProactiveScheduler)
- [ ] **幂等性测试**：连续发送 `/start` -> `/stop` -> `/start` 是否会导致计时器叠加或状态残留？
- [ ] **非法进入**：未通过 `SessionController` 校验的用户是否绝对无法触达 `ChatService`？

### ⚠️ 常见坑点
- **状态不一致**：`SessionController` 认为会话结束了，但 `ChatService` 还在运行异步 LLM 请求。
- **清理不彻底**：仅删除了 Session ID，但后台线程（如计时器）依然存活并尝试发送消息。

### 🔍 观测建议
- `[SESSION] START | user_id: {id}`
- `[SESSION] STOP | user_id: {id} | reason: {manual/private_mode_enforced}`
- `[SESSION] DENIED | user_id: {id} | reason: {private_mode/inactive}`

---

## 二、 交互节奏管理 (Interaction & Buffering)
**关联组件**：[interaction.py](file:///d:/Whoami/Nonebot/Telegram_Chatbot/src/core/interaction.py)
**稳定性目标**：防止消息风暴，模拟自然人类交互节奏。

### ✅ 检查点
- [ ] **消息合并**：用户快速发送 3 条消息，系统是否正确合并为 1 次 `ChatService` 调用？
- [ ] **竞态条件**：在高频输入下，`buffer_lock` 是否有效防止了消息丢失或顺序错乱？
- [ ] **即时中断**：用户发送消息后立即 `/stop`，缓冲区是否被清空且不再触发后续发送？
- [ ] **多用户隔离**：多用户并发聊天时，是否存在缓冲区“串号”现象？

### ⚠️ 常见坑点
- **计时器泄漏**：`Timer.cancel()` 被调用但未从管理字典中移除引用。
- **异常导致阻塞**：处理逻辑抛出异常后，未清理对应的计时器锁，导致该用户永久无法再次触发交互。

### 🔍 观测建议
- `[BUFFER] ADD | user_id: {id} | current_size: {n}`
- `[BUFFER] FLUSH | user_id: {id} | total_len: {chars}`
- `[TIMER] RESET | user_id: {id} | delay: {seconds}s`

---

## 三、 核心聊天业务 (ChatService & LLM)
**关联组件**：[chat_service.py](file:///d:/Whoami/Nonebot/Telegram_Chatbot/src/core/chat_service.py), [llm_client.py](file:///d:/Whoami/Nonebot/Telegram_Chatbot/src/core/llm_client.py)
**稳定性目标**：保证核心链路的健壮性，绝不因外部 API 失败而崩溃。

### ✅ 检查点
- [ ] **API 容错**：LLM 超时或返回非 200 状态时，`ChatService` 是否抛出可控异常而非返回空字符串？
- [ ] **状态回滚**：LLM 调用失败时，已添加到 Context 的 User Message 是否需要回滚（避免上下文单向增长）？
- [ ] **长度保护**：当短期上下文达到 Token 上限时，是否执行了正确的截断或摘要逻辑？
- [ ] **并发锁**：针对同一用户的多次 `ChatService` 调用是否由 `context_lock` 串行化？

### ⚠️ 常见坑点
- **半写入状态**：异常发生后，系统状态处于“用户消息已存入，但 AI 回复丢失”的尴尬境地。
- **阻塞等待**：LLM 客户端没有设置合理的 `timeout`，导致整个处理线程被无限挂起。

### 🔍 观测建议
- `[CHAT] CALL | user_id: {id} | context_turns: {n}`
- `[LLM] REQ | model: {name} | tokens: {n}`
- `[LLM] FAIL | error: {timeout/auth/rate_limit}`

---

## 四、 长期记忆系统 (Memory & Summary)
**关联组件**：[memory_ingest.py](file:///d:/Whoami/Nonebot/Telegram_Chatbot/src/core/memory_ingest.py), [summary_contract.py](file:///d:/Whoami/Nonebot/Telegram_Chatbot/src/core/summary_contract.py)
**稳定性目标**：数据的一致性与异步处理的解耦。

### ✅ 检查点
- [ ] **静默触发**：极短的会话（如 1-2 轮）是否正确跳过了总结逻辑？
- [ ] **异步解耦**：总结失败是否会阻塞或影响当前的对话交互？
- [ ] **重试限额**：总结 API 失败后，是否有最大重试次数限制？
- [ ] **重复注入**：同一段会话是否会被多次错误地总结和存入数据库？

### ⚠️ 常见坑点
- **强耦合依赖**：把记忆写入当成同步操作，数据库锁直接导致用户无法接收消息。
- **资源冲突**：总结任务读取 Context 时，用户恰好发送了新消息导致的数据竞态。

### 🔍 观测建议
- `[SUMMARY] TRIGGER | user_id: {id} | reason: {session_end/idle}`
- `[SUMMARY] SKIP | user_id: {id} | reason: {too_short}`
- `[MEMORY] INGEST | user_id: {id} | status: {success/fail}`

---

## 五、 主动消息 (Proactive Messaging)
**关联组件**：[proactive_service.py](file:///d:/Whoami/Nonebot/Telegram_Chatbot/src/core/proactive_service.py), [proactive_messaging.py](file:///d:/Whoami/Nonebot/Telegram_Chatbot/src/bot/proactive_messaging.py)
**稳定性目标**：控制“边界感”，防止变成垃圾消息源。

### ✅ 检查点
- [ ] **状态依赖**：主动消息发送前，是否二次校验了 Session 仍然处于 `active` 状态？
- [ ] **计时器清理**：用户主动发起聊天时，是否取消了原本计划中的主动发送计时器？
- [ ] **失败处理**：生成内容失败时，系统是否选择静默失败而非发送错误信息给用户？

### ⚠️ 常见坑点
- **计时器爆炸**：逻辑错误导致每轮对话都开启一个新的 Proactive Timer 却没清理旧的。
- **身份越界**：主动消息使用了过期的快照数据。

---

## 六、 系统全局与资源 (System Health)
**稳定性目标**：长期运行的可靠性。

### ✅ 检查点
- [ ] **配置强校验**：错误的 YAML 配置或缺失的环境变量是否在系统启动阶段就触发 `fail-fast`？
- [ ] **内存足迹**：连续运行 24 小时后，内存占用是否稳定（是否存在 dict/list 持续增长未清理）？
- [ ] **退出清理**：接收到 `SIGINT` (Ctrl+C) 后，系统是否优雅关闭并保存了必要状态？

---

## 🧠 工程师自学指南 (How to use)

1. **不要一次性全测**：每天选取 1 个模块，故意制造“极端情况”。
2. **看日志而非看代码**：如果日志无法清晰解释发生了什么，说明你的日志打得不够好。
3. **补 Guard 而非补功能**：每发现一个 bug，首先想如何通过代码结构防止它再次发生，而不仅仅是修复它。

**训练目标**：在系统出问题前，就知道它会怎么死。