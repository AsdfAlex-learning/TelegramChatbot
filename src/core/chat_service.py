"""
文件职责：聊天服务
核心业务逻辑层，负责协调 LLM 调用、上下文管理和记忆更新。
作为 Core 的主要入口点，处理用户输入并返回 AI 响应。
"""

import threading
import time
import logging
from typing import Dict, Tuple, Set, Optional, List

from src.core.config_loader import ConfigLoader
from src.core.context import ConversationContext
from src.core.llm_client import LLMClient
from src.storage.memory import LongTermMemory
from src.core.session_controller import SessionController

class ChatService:
    def __init__(self, session_controller: SessionController):
        self._initialize(session_controller)

    def _initialize(self, session_controller: SessionController):
        self.config_loader = ConfigLoader()
        self.system_config = self.config_loader.system_config
        self.prompt_manager = self.config_loader.prompt_manager
        
        self.llm_client = LLMClient(self.system_config)
        self.session_controller = session_controller
        
        # 状态管理
        self.chat_contexts: Dict[int, ConversationContext] = {}
        self.user_memories: Dict[int, LongTermMemory] = {}
        self.user_prompt_cache: Dict[int, Tuple[str, float]] = {}
        self.user_message_counts: Dict[int, int] = {}
        
        # 锁
        self.context_lock = threading.Lock()  # 用于 chat_contexts
        self.memory_lock = threading.Lock()   # 用于 user_memories
        self.state_lock = threading.Lock()    # 用于其他状态 (counts, cache)

    def stop_chat(self, user_id: int):
        """停止聊天并清理资源。"""
        self.clean_resources(user_id)

    def clean_resources(self, user_id: int):
        """清理用户资源（会话停止时调用）。"""
        with self.state_lock:
            if user_id in self.user_message_counts:
                del self.user_message_counts[user_id]
            if user_id in self.user_prompt_cache:
                del self.user_prompt_cache[user_id]
        
        with self.context_lock:
            if user_id in self.chat_contexts:
                del self.chat_contexts[user_id]

    def get_context(self, user_id: int) -> ConversationContext:
        """获取或创建用户的对话上下文。"""
        with self.context_lock:
            if user_id not in self.chat_contexts:
                self.chat_contexts[user_id] = ConversationContext()
            return self.chat_contexts[user_id]

    def get_user_memory(self, user_id: int) -> LongTermMemory:
        """获取或创建用户的长期记忆实例。"""
        with self.memory_lock:
            if user_id not in self.user_memories:
                self.user_memories[user_id] = LongTermMemory(user_id)
            return self.user_memories[user_id]

    def add_user_message_to_context(self, user_id: int, message: str):
        """将用户消息添加到上下文，但不触发回复。"""
        ctx = self.get_context(user_id)
        ctx.add_message("user", message)

    def add_assistant_message_to_context(self, user_id: int, message: str):
        """将助手消息添加到上下文。"""
        ctx = self.get_context(user_id)
        ctx.add_message("assistant", message)

    def process_user_input(self, user_id: int, user_input: str) -> str:
        """
        处理用户输入：
        1. 添加到上下文
        2. 构建 Prompt (包含记忆)
        3. 调用 LLM
        4. 添加回复到上下文
        5. 触发记忆提取（如需）
        6. 返回回复
        """
        # 1. 添加到上下文
        self.add_user_message_to_context(user_id, user_input)
        
        # 2. 准备上下文和记忆
        conversation_str = self.get_context(user_id).format(exclude_last_n=1)
        user_summary = self._get_user_prompt_summary(user_id)
        
        # 3. 构建 Prompt
        final_prompt = self.prompt_manager.build_prompt(
            user_message=user_input,
            memory=user_summary,
            conversation=conversation_str
        )
        
        # 4. 调用 LLM
        try:
            response = self.llm_client.chat_completion(
                messages=[{"role": "user", "content": final_prompt}]
            )
        except Exception as e:
            logging.error(f"[ChatService] LLM 错误: {e}")
            raise e
            
        # 5. 添加回复到上下文
        self.add_assistant_message_to_context(user_id, response)
        
        # 6. 更新记忆 (异步或同步？目前是同步)
        self._update_memories(user_id, user_input, response)
        
        return response

    def _get_user_prompt_summary(self, user_id: int) -> str:
        """
        获取用于 Prompt 的记忆摘要。
        如果缓存有效则使用缓存。
        """
        with self.state_lock:
            cache = self.user_prompt_cache.get(user_id)
            if cache:
                content, timestamp = cache
                # TODO: 实现更智能的缓存失效逻辑（例如基于时间或更新事件）
                # 目前只是简单返回
                pass 

        # 加载记忆
        memory = self.get_user_memory(user_id)
        valid_memories = memory.load_valid_memories()
        
        if not valid_memories:
            return "暂无特殊记忆"
            
        # 按重要性排序 (索引 3)
        sorted_memories = sorted(valid_memories, key=lambda x: x[3], reverse=True)
        top_memories = sorted_memories[:20] # 限制前 20 条
        
        mem_text = "\n".join([f"- {m[1]} (关键词:{m[2]})" for m in top_memories])
        return mem_text

    def _update_memories(self, user_id: int, user_input: str, response: str):
        """
        基于交互更新长期记忆。
        简单逻辑：计数消息，每 N 条触发一次提取。
        """
        with self.state_lock:
            count = self.user_message_counts.get(user_id, 0) + 1
            self.user_message_counts[user_id] = count
            
        # 每 5 条消息提取一次
        if count % 5 == 0:
            # TODO: 实现真正的记忆提取逻辑
            # 这里应该调用 LLM 来提取事实，并使用 MemoryManager 存储
            # 建议使用异步任务来避免阻塞聊天
            pass
