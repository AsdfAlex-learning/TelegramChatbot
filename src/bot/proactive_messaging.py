import threading
import time
import random
import logging
from typing import Callable, Dict, Optional
from src.core.proactive_service import ProactiveService
from src.core.chat_service import ChatService

class ProactiveScheduler:
    """
    主动消息调度器。
    职责:
    1. 计时 (决定何时检查)。
    2. 调度 (决定延迟时间)。
    3. 执行 (通过 I/O 回调发送消息)。
    
    将“内容决策”委托给 ProactiveService。
    """
    def __init__(self, 
                 proactive_service: ProactiveService, 
                 chat_service: ChatService,
                 sender: Callable[[int, str], None]):
        self.proactive_service = proactive_service
        self.chat_service = chat_service
        self.sender = sender
        
        self.check_timers: Dict[int, threading.Timer] = {}
        self.send_timers: Dict[int, threading.Timer] = {}
        self.lock = threading.Lock()
        
        # 配置 (时间间隔)
        self.check_interval_min = 1800  # 30 分钟
        self.check_interval_max = 7200  # 2 小时
        self.send_delay_min = 60        # 1 分钟
        self.send_delay_max = 600       # 10 分钟

    def start(self, user_id: int):
        """为用户启动调度器。"""
        self.on_user_activity(user_id)

    def stop(self, user_id: int):
        """停止用户的调度器。"""
        with self.lock:
            if user_id in self.check_timers:
                self.check_timers[user_id].cancel()
                del self.check_timers[user_id]
            if user_id in self.send_timers:
                self.send_timers[user_id].cancel()
                del self.send_timers[user_id]
        logging.info(f"[ProactiveScheduler] 已停止用户 {user_id}")

    def on_user_activity(self, user_id: int):
        """
        当用户活跃时调用。
        重置检查计时器并取消任何挂起的主动发送。
        """
        with self.lock:
            # 取消挂起的发送 (不要打断用户)
            if user_id in self.send_timers:
                logging.info(f"[ProactiveScheduler] 用户 {user_id} 活跃，取消挂起的消息。")
                self.send_timers[user_id].cancel()
                del self.send_timers[user_id]
            
            # 取消现有的检查计时器
            if user_id in self.check_timers:
                self.check_timers[user_id].cancel()
            
            # 调度下一次检查
            delay = random.uniform(self.check_interval_min, self.check_interval_max)
            timer = threading.Timer(delay, self._check_callback, args=[user_id])
            timer.daemon = True
            timer.start()
            self.check_timers[user_id] = timer
            logging.info(f"[ProactiveScheduler] 已调度 {user_id} 的下一次检查，在 {delay:.1f}s 后")

    def _check_callback(self, user_id: int):
        """检查计时器的回调。"""
        with self.lock:
            if user_id in self.check_timers:
                del self.check_timers[user_id]

        # 1. 询问 Core: 我们应该触发吗？
        if not self.proactive_service.should_trigger(user_id):
            self.on_user_activity(user_id) # 重新调度下一次检查
            return

        # 2. 询问 Core: 生成内容
        content = self.proactive_service.generate_content(user_id)
        if not content:
            self.on_user_activity(user_id)
            return

        # 3. 调度发送
        delay = random.uniform(self.send_delay_min, self.send_delay_max)
        logging.info(f"[ProactiveScheduler] 正在调度发送给 {user_id}，在 {delay:.1f}s 后。内容: {content[:20]}...")
        
        timer = threading.Timer(delay, self._execute_send, args=[user_id, content])
        timer.daemon = True
        timer.start()
        
        with self.lock:
            self.send_timers[user_id] = timer

    def _execute_send(self, user_id: int, content: str):
        """Execute the actual send."""
        with self.lock:
            if user_id in self.send_timers:
                del self.send_timers[user_id]
        
        try:
            logging.info(f"[ProactiveScheduler] Sending to {user_id}: {content}")
            
            # Use the injected sender (e.g., Telegram sender)
            if self.sender:
                self.sender(user_id, content)
                
                # Update Context (Core State)
                self.chat_service.add_assistant_message_to_context(user_id, content)
            else:
                logging.error("[ProactiveScheduler] No sender configured!")
                
        except Exception as e:
            logging.error(f"[ProactiveScheduler] Send failed: {e}")
        
        # Reset loop
        self.on_user_activity(user_id)
