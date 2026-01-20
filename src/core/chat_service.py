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
        
        # State Management
        self.chat_contexts: Dict[int, ConversationContext] = {}
        self.user_memories: Dict[int, LongTermMemory] = {}
        self.user_prompt_cache: Dict[int, Tuple[str, float]] = {}
        self.user_message_counts: Dict[int, int] = {}
        
        # Locks
        self.context_lock = threading.Lock()  # For chat_contexts
        self.memory_lock = threading.Lock()   # For user_memories
        self.state_lock = threading.Lock()    # For other state (counts, cache)

    def stop_chat(self, user_id: int):
        """Stop chat and clean up resources."""
        self.clean_resources(user_id)

    def clean_resources(self, user_id: int):
        """Clean up resources for a user (called when session stops)."""
        with self.state_lock:
            if user_id in self.user_message_counts:
                del self.user_message_counts[user_id]
            if user_id in self.user_prompt_cache:
                del self.user_prompt_cache[user_id]
        
        with self.context_lock:
            if user_id in self.chat_contexts:
                del self.chat_contexts[user_id]

    def get_context(self, user_id: int) -> ConversationContext:
        """Get or create conversation context for a user."""
        with self.context_lock:
            if user_id not in self.chat_contexts:
                self.chat_contexts[user_id] = ConversationContext()
            return self.chat_contexts[user_id]

    def get_user_memory(self, user_id: int) -> LongTermMemory:
        """Get or create LongTermMemory instance for a user."""
        with self.memory_lock:
            if user_id not in self.user_memories:
                self.user_memories[user_id] = LongTermMemory(user_id)
            return self.user_memories[user_id]

    def add_user_message_to_context(self, user_id: int, message: str):
        """Add a user message to the context without triggering a reply."""
        ctx = self.get_context(user_id)
        ctx.add_message("user", message)

    def add_assistant_message_to_context(self, user_id: int, message: str):
        """Add an assistant message to the context."""
        ctx = self.get_context(user_id)
        ctx.add_message("assistant", message)

    def process_user_input(self, user_id: int, user_input: str) -> str:
        """
        Process user input:
        1. Add to context
        2. Build prompt (with memory)
        3. Call LLM
        4. Add response to context
        5. Trigger memory extraction if needed
        6. Return response
        """
        # 1. Add to context
        self.add_user_message_to_context(user_id, user_input)
        
        # 2. Prepare Context & Memory
        conversation_str = self.get_context(user_id).format(exclude_last_n=1)
        user_summary = self._get_user_prompt_summary(user_id)
        
        # 3. Build Prompt
        final_prompt = self.prompt_manager.build_prompt(
            user_message=user_input,
            memory=user_summary,
            conversation=conversation_str
        )
        
        # 4. Call LLM
        try:
            response = self.llm_client.chat_completion(
                messages=[{"role": "user", "content": final_prompt}]
            )
        except Exception as e:
            logging.error(f"[ChatService] LLM Error: {e}")
            raise e
            
        # 5. Add response to context
        self.add_assistant_message_to_context(user_id, response)
        
        # 6. Update memory (Async or Sync? For now Sync)
        self._update_memories(user_id, user_input, response)
        
        return response

    def _get_user_prompt_summary(self, user_id: int) -> str:
        """
        Get summarized memory for prompt.
        Uses cache if valid.
        """
        with self.state_lock:
            cache = self.user_prompt_cache.get(user_id)
            if cache:
                content, timestamp = cache
                # Cache valid for 5 mins? Or strictly based on updates?
                # For now, let's just return it. 
                # In a real system, we'd invalidate cache on memory update.
                pass 

        # Load memories
        memory = self.get_user_memory(user_id)
        valid_memories = memory.load_valid_memories()
        
        if not valid_memories:
            return "暂无特殊记忆"
            
        # Sort by importance (index 3)
        sorted_memories = sorted(valid_memories, key=lambda x: x[3], reverse=True)
        top_memories = sorted_memories[:20] # Limit to top 20
        
        mem_text = "\n".join([f"- {m[1]} (关键词:{m[2]})" for m in top_memories])
        return mem_text

    def _update_memories(self, user_id: int, user_input: str, response: str):
        """
        Update long-term memory based on interaction.
        Simple logic: Count messages, trigger extraction every N messages.
        """
        with self.state_lock:
            count = self.user_message_counts.get(user_id, 0) + 1
            self.user_message_counts[user_id] = count
            
        # Extract every 5 messages
        if count % 5 == 0:
            # Trigger extraction (simplified)
            # In a full system, this would call an LLM to extract facts
            pass
