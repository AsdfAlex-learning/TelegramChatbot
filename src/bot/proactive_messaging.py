import threading
import time
import random
import logging
import requests
from src.storage.memory import LongTermMemory

class ProactiveScheduler:
    def __init__(self, bot, config, prompt_manager, chat_context, context_lock, memory_provider):
        self.bot = bot
        self.config = config
        self.prompt_manager = prompt_manager
        self.chat_context = chat_context
        self.context_lock = context_lock
        self.memory_provider = memory_provider
        
        # Standardize API Config (OpenAI Compatible)
        if hasattr(config, "llm"):
            self.api_key = config.llm.api_key
            self.api_url = config.llm.api_url
            self.model = config.llm.model
        elif hasattr(config, "deepseek"):
            # Legacy support
            self.api_key = config.deepseek.api_key
            self.api_url = config.deepseek.api_url
            self.model = "deepseek-chat"
        else:
            # Dict fallback
            llm_cfg = config.get("llm", config.get("deepseek", {}))
            self.api_key = llm_cfg.get("api_key")
            self.api_url = llm_cfg.get("api_url")
            self.model = llm_cfg.get("model", "deepseek-chat")
        
        self.check_timers = {}  # user_id -> Timer (Main Loop)
        self.send_timers = {}   # user_id -> Timer (Pending Send)
        self.lock = threading.Lock()
        
        # Configuration defaults (可后续移至配置文件)
        # 检查间隔：30分钟 ~ 2小时
        self.check_interval_min = 1800 
        self.check_interval_max = 7200
        # 发送概率：30%
        self.send_prob = 0.3
        # 发送延迟：1分钟 ~ 10分钟
        self.send_delay_min = 60
        self.send_delay_max = 600

    def start(self, user_id):
        """为用户开启主动消息循环"""
        self.on_user_activity(user_id)

    def stop(self, user_id):
        """停止用户的主动消息循环"""
        with self.lock:
            if user_id in self.check_timers:
                self.check_timers[user_id].cancel()
                del self.check_timers[user_id]
            if user_id in self.send_timers:
                self.send_timers[user_id].cancel()
                del self.send_timers[user_id]
        logging.info(f"[Proactive] Stopped scheduler for user {user_id}")

    def on_user_activity(self, user_id):
        """
        用户有活动时调用（发消息）。
        1. 取消任何待发送的主动消息（避免打断用户）。
        2. 重置下一次检查的计时器。
        """
        with self.lock:
            # 如果正在等待发送主动消息，取消它
            if user_id in self.send_timers:
                logging.info(f"[Proactive] User {user_id} active, cancelling pending proactive message.")
                self.send_timers[user_id].cancel()
                del self.send_timers[user_id]
            
            # 取消现有的检查计时器
            if user_id in self.check_timers:
                self.check_timers[user_id].cancel()
            
            # 规划下一次检查
            delay = random.uniform(self.check_interval_min, self.check_interval_max)
            
            timer = threading.Timer(delay, self._check_and_trigger, args=[user_id])
            timer.daemon = True
            timer.start()
            self.check_timers[user_id] = timer
            logging.info(f"[Proactive] Scheduled next check for {user_id} in {delay:.1f}s")

    def _check_and_trigger(self, user_id):
        """检查逻辑：随机决定是否发送"""
        with self.lock:
            if user_id in self.check_timers:
                del self.check_timers[user_id]

        # 随机判定
        if random.random() > self.send_prob:
            logging.info(f"[Proactive] Check for {user_id}: Decided NOT to send.")
            self.on_user_activity(user_id) # 重新调度下一轮
            return

        # 生成内容
        try:
            content = self._generate_proactive_message(user_id)
            if not content:
                self.on_user_activity(user_id)
                return
                
            # 规划发送时间
            delay = random.uniform(self.send_delay_min, self.send_delay_max)
            logging.info(f"[Proactive] Check for {user_id}: Sending in {delay:.1f}s. Content: {content[:20]}...")
            
            timer = threading.Timer(delay, self._execute_send, args=[user_id, content])
            timer.daemon = True
            timer.start()
            
            with self.lock:
                self.send_timers[user_id] = timer
                
        except Exception as e:
            logging.error(f"[Proactive] Error in check logic: {e}")
            self.on_user_activity(user_id)

    def _execute_send(self, user_id, content):
        """执行发送"""
        with self.lock:
            if user_id in self.send_timers:
                del self.send_timers[user_id]
        
        try:
            logging.info(f"[Proactive] Sending message to {user_id}: {content}")
            
            # 简单的重试逻辑
            sent = False
            for _ in range(3):
                try:
                    self.bot.send_message(user_id, content)
                    sent = True
                    break
                except Exception as e:
                    logging.warning(f"[Proactive] Send failed, retrying: {e}")
                    time.sleep(2)
            
            if sent:
                # 记录到上下文，以便后续对话有记忆
                with self.context_lock:
                    if user_id in self.chat_context:
                        self.chat_context[user_id].add_message("assistant", content)
            
        except Exception as e:
            logging.error(f"[Proactive] Failed to send: {e}")
        
        # 重置循环
        self.on_user_activity(user_id)

    def _generate_proactive_message(self, user_id):
        # 获取记忆
        memory = self.memory_provider(user_id)
        valid_memories = memory.load_valid_memories()
        
        if not valid_memories:
            return None

        # 按重要度排序（index 3）
        sorted_memories = sorted(valid_memories, key=lambda x: x[3], reverse=True)
        top_memories = sorted_memories[:3] # 取前3条
        
        mem_text = "\n".join([f"- {m[1]} (关键词:{m[2]})" for m in top_memories])
        
        instruction = (
            "（系统指令：请忽略上文的‘回复用户’要求。现在是空闲时间，请根据【用户记忆】主动发起一个温馨的话题。"
            "语气自然亲切，不要太生硬，一两句话即可。）"
        )
        
        final_prompt = self.prompt_manager.build_prompt(
            user_message=instruction,
            memory=mem_text,
            conversation="暂无"
        )
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": final_prompt}
            ]
        }
        
        try:
            resp = requests.post(self.api_url, json=data, headers=headers, timeout=30)
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            logging.error(f"[Proactive] Generation failed: {e}")
            return None
