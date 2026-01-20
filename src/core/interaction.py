import threading
import time
import random
import logging
from typing import Callable, List, Dict, Optional
from src.core.config_loader import ConfigLoader
from src.core.chat_service import ChatService

from src.core.session_controller import SessionController, AccessResult

class InteractionManager:
    def __init__(self, chat_service: ChatService, session_controller: SessionController):
        self._initialize(chat_service, session_controller)

    def _initialize(self, chat_service: ChatService, session_controller: SessionController):
        self.chat_service = chat_service
        self.session_controller = session_controller
        self.config_loader = ConfigLoader()
        self.system_config = self.config_loader.system_config
        
        # Buffer State
        self.user_message_buffer: Dict[int, List[str]] = {}
        self.user_timers: Dict[int, threading.Timer] = {}
        self.buffer_lock = threading.Lock()
        
        # Callback for sending messages (user_id, text) -> None
        self.sender: Optional[Callable[[int, str], None]] = None

    def set_sender(self, sender_func: Callable[[int, str], None]):
        """
        Set the callback function to send messages.
        sender_func should handle the actual I/O (e.g., Telegram send).
        """
        self.sender = sender_func

    def add_user_message(self, user_id: int, message_text: str):
        """
        Add a user message to the buffer and schedule processing.
        Includes permission check.
        """
        access = self.session_controller.can_continue_session(user_id)
        
        if access == AccessResult.DENIED_PRIVATE:
            logging.info(f"[Interaction] Ignored message from {user_id} (Private Mode)")
            # Optionally send a "system busy" or "unauthorized" message here if desired
            # For now, we silent ignore or maybe notify once? 
            # Given main.py delegates completely, we should probably reply if it's a hard deny
            if self.sender:
                self.sender(user_id, "🔒 机器人处于私有模式，您无权访问。")
            return
            
        if access == AccessResult.DENIED_INACTIVE:
            logging.info(f"[Interaction] Ignored message from {user_id} (Session Inactive)")
            # Silent ignore for inactive sessions is standard behavior (don't reply to random messages)
            return

        with self.buffer_lock:
            if user_id not in self.user_message_buffer:
                self.user_message_buffer[user_id] = []
            
            self.user_message_buffer[user_id].append(message_text)
            logging.info(f"[Interaction] User {user_id} added message: {message_text} | Buffer size: {len(self.user_message_buffer[user_id])}")
            
            # Reset timer
            if user_id in self.user_timers:
                self.user_timers[user_id].cancel()
            
            # Get delay from config
            try:
                min_time = self.system_config.message_buffer.collect_min_time
                max_time = self.system_config.message_buffer.collect_max_time
            except AttributeError:
                # Fallback defaults
                min_time = 1.0
                max_time = 3.0
                
            collect_time = random.uniform(min_time, max_time)
            
            timer = threading.Timer(collect_time, self._process_buffer, args=[user_id])
            timer.daemon = True
            timer.start()
            self.user_timers[user_id] = timer
            logging.info(f"[Interaction] Scheduled processing for user {user_id} in {collect_time:.1f}s")

    def clear_user_state(self, user_id: int):
        """
        Clear buffer and timers for a user (e.g., when stopping chat).
        """
        with self.buffer_lock:
            if user_id in self.user_message_buffer:
                del self.user_message_buffer[user_id]
            if user_id in self.user_timers:
                self.user_timers[user_id].cancel()
                del self.user_timers[user_id]

    def _process_buffer(self, user_id: int):
        """
        Process the buffered messages for a user.
        """
        with self.buffer_lock:
            # Remove timer from dict as it has triggered
            if user_id in self.user_timers:
                del self.user_timers[user_id]
            
            # Get and clear messages
            messages = self.user_message_buffer.get(user_id, [])
            if not messages:
                return
            del self.user_message_buffer[user_id]
        
        # Combine messages
        full_text = "\n".join(messages)
        logging.info(f"[Interaction] Processing buffered messages for {user_id}: {full_text[:50]}...")
        
        try:
            # Call ChatService
            response = self.chat_service.process_user_input(user_id, full_text)
            
            # Split and Send
            self._send_response_chunks(user_id, response)
            
        except Exception as e:
            logging.error(f"[Interaction] Error processing buffer for {user_id}: {e}")
            if self.sender:
                # 友好的错误提示，不暴露内部异常
                self.sender(user_id, "⚠️ 抱歉，我现在有点晕，请稍后再试。")

    def _send_response_chunks(self, user_id: int, text: str):
        """
        Split response by '$' or newline, and send chunks with delay.
        """
        if not text:
            return

        # Split logic: Priority to '$', then newlines
        # The prompt usually instructs to use '$' for splitting
        chunks = []
        if '$' in text:
            parts = text.split('$')
            for p in parts:
                if p.strip():
                    chunks.append(p.strip())
        else:
            # Fallback to newline splitting if long? Or just send as is?
            # User requirement mentioned "Split by $ split by \n" logic extraction.
            # Let's support both.
            lines = text.split('\n')
            for line in lines:
                if line.strip():
                    chunks.append(line.strip())
        
        if not chunks:
            chunks = [text]

        # Send loop
        for i, chunk in enumerate(chunks):
            if self.sender:
                self.sender(user_id, chunk)
            
            # Delay between chunks
            if i < len(chunks) - 1:
                # Calculate reading time based on length?
                # Simple logic: 0.5s + 0.05s per char, max 3s
                delay = min(3.0, 0.5 + len(chunk) * 0.05)
                time.sleep(delay)
