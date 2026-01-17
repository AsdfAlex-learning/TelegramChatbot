import nonebot
import os
import threading
import telebot
import requests
import time
import random
import json
import sys
import sqlite3
import csv
import logging
from datetime import datetime, timedelta
from nonebot import on_command
from nonebot.adapters import Message
from nonebot.params import CommandArg
from nonebot import get_driver
from src.storage.memory import LongTermMemory
from src.core.api_registry import APIRegistry
from src.core.config_loader import ConfigLoader
from src.bot.proactive_messaging import ProactiveScheduler
from src.core.context import ConversationContext

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

nonebot.init(env_file=os.path.join(PROJECT_ROOT, ".env.prod"))
driver = get_driver()

config_loader = ConfigLoader()
system_config = config_loader.system_config

TELEGRAM_TOKEN = system_config.telegram.bot_token
LLM_API_KEY = system_config.llm.api_key
LLM_API_URL = system_config.llm.api_url
LLM_MODEL = system_config.llm.model
OWNER_ID = system_config.telegram.owner_id

bot_is_private = system_config.bot.private_mode_default  # 默认开启私有模式，仅Owner可用

ai_chat_active = set()  # 存储已开启AI对话的用户ID
chat_lock = threading.Lock()  # 线程锁保证状态安全
chat_context = {}  # 格式：{user_id: [{"role": "...", "content": "..."}]}
context_lock = threading.Lock()  # 上下文操作的线程锁
user_message_count = {}  # 记录对话轮数：{user_id: count}
user_prompt_cache = {}  # USER_PROMPT缓存：{user_id: (prompt, cache_time)}

# ========== 消息缓冲相关配置 ==========
user_message_buffer = {}  # {user_id: [msg1, msg2, ...]}
user_timers = {}  # {user_id: timer_thread}
buffer_lock = threading.Lock()

# 初始化Telegram机器人
tb_bot = telebot.TeleBot(TELEGRAM_TOKEN)

def safe_send_message(chat_id, text, max_attempts=3):
    backoff = 1
    for attempt in range(max_attempts):
        try:
            tb_bot.send_message(chat_id, text)
            return True
        except requests.exceptions.RequestException as e:
            if attempt == max_attempts - 1:
                print(f"[Telegram] 发送失败（chat_id={chat_id}）：{e}")
                logging.error(f"[Telegram] 发送失败（chat_id={chat_id}）：{e}")
                return False
            time.sleep(backoff)
            backoff = min(backoff * 2, 10)
        except Exception as e:
            print(f"[Telegram] 发送异常（chat_id={chat_id}）：{e}")
            logging.error(f"[Telegram] 发送异常（chat_id={chat_id}）：{e}")
            return False

# ========== 长期记忆模块 ==========
# LongTermMemory 类已移动至 src/storage/memory.py

# 全局存储用户记忆实例
user_memories = {}
memory_lock = threading.Lock()

def get_user_memory(user_id):
    with memory_lock:
        if user_id not in user_memories:
            user_memories[user_id] = LongTermMemory(user_id)
        return user_memories[user_id]

# 初始化主动消息调度器
proactive_scheduler = ProactiveScheduler(tb_bot, system_config, config_loader.prompt_manager, chat_context, context_lock, get_user_memory)

# ====================== LLM API调用函数 ======================
def call_llm_api(user_id: int, prompt: str, extra_context: str = "") -> str:
    """调用OpenAI Compatible API获取回复，支持添加额外记忆上下文"""
    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json"
    }
    
    with context_lock:
        if user_id not in chat_context:
            chat_context[user_id] = ConversationContext()
        
        chat_context[user_id].add_message("user", prompt)

    # Prepare Conversation String (History excluding current message)
    conversation_str = chat_context[user_id].format(exclude_last_n=1)

    # Prepare Memory String
    user_summary = "用户信息加载中..."
    if user_id in user_prompt_cache:
        user_summary, _ = user_prompt_cache[user_id]
    else:
        user_summary = generate_user_prompt(user_id)

    memory_str = user_summary
    if extra_context:
        memory_str += f"\n\n【相关记忆细节】\n{extra_context}"

    # Build Final Prompt using PromptManager
    final_prompt = config_loader.prompt_manager.build_prompt(
        user_message=prompt,
        memory=memory_str,
        conversation=conversation_str
    )

    data = {
        "model": LLM_MODEL,
        "messages": [{"role": "user", "content": final_prompt}],
        "temperature": system_config.llm.temperature,
        "max_tokens": system_config.llm.max_tokens
    }
    
    try:
        response = requests.post(LLM_API_URL, headers=headers, json=data, timeout=30)
        response.raise_for_status()
        result = response.json()
        assistant_reply = result["choices"][0]["message"]["content"].strip()

        with context_lock:
            chat_context[user_id].add_message("assistant", assistant_reply)
        
        return assistant_reply
    
    except requests.exceptions.RequestException as e:
        return f"API调用失败：{str(e)}"
    except KeyError as e:
        return f"API返回格式异常：缺少字段 {str(e)}"

def generate_user_prompt(user_id):
    """生成USER_PROMPT（核心层+动态层）"""
    if user_id in user_prompt_cache:
        prompt, cache_time = user_prompt_cache[user_id]
        if time.time() - cache_time < 86400:
            return prompt
    
    memories = get_user_memory(user_id).load_valid_memories()
    mem_descriptions = []
    for mem in memories:
        mem_descriptions.append(f"事件：{mem[1]}，关键词：{mem[2]}，重要度：{mem[3]}")
    
    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": "根据以下用户记忆，生成≤200字的USER_PROMPT，分核心层（永久属性）和动态层（临时事件）。核心层必加，动态层仅在相关时提及。"},
            {"role": "user", "content": "\n".join(mem_descriptions)}
        ]
    }
    
    try:
        response = requests.post(LLM_API_URL, headers=headers, json=data, timeout=30)
        user_prompt = response.json()["choices"][0]["message"]["content"].strip()
        user_prompt_cache[user_id] = (user_prompt, time.time())
        return user_prompt
    except Exception as e:
        print(f"生成USER_PROMPT失败：{e}")
        logging.error(f"生成USER_PROMPT失败：{e}")
        return "用户信息加载中..."

def extract_keywords(text):
    """提取文本关键词（简化版，实际可优化）"""
    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": "提取输入文本的核心关键词，用逗号分隔，不超过5个词。"},
            {"role": "user", "content": text}
        ]
    }
    try:
        response = requests.post(LLM_API_URL, headers=headers, json=data, timeout=10)
        return response.json()["choices"][0]["message"]["content"].split(',')
    except:
        return text.split()[:5]

def extract_new_memories(user_id):
    """从最近对话中提取新记忆"""
    with context_lock:
        if user_id not in chat_context:
            return []
        recent_dialogs = chat_context[user_id].get_raw_history()[-20:]
    
    dialog_text = "\n".join([f"{d['role']}: {d['content']}" for d in recent_dialogs])
    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": 
                """从对话中提取用户的重要信息，按格式返回：
                事件（YYYY-MM-DD + 具体事件）,关键词（逗号分隔）,重要度(0-100),有效期（天，365=永久）
                仅保留重要信息，普通闲聊忽略。
                """},
            {"role": "user", "content": dialog_text}
        ]
    }
    
    try:
        response = requests.post(LLM_API_URL, headers=headers, json=data, timeout=30)
        result = response.json()["choices"][0]["message"]["content"]
        memories = []
        for line in result.split('\n'):
            if line.strip():
                parts = line.split(',')
                if len(parts) == 4:
                    memories.append((parts[0].strip(), parts[1].strip(), int(parts[2].strip()), int(parts[3].strip())))
        return memories
    except Exception as e:
        print(f"提取新记忆失败：{e}")
        logging.error(f"提取新记忆失败：{e}")
        return []

# ========== 消息打包与发送核心函数 ==========
def process_user_messages(user_id):
    """处理用户缓冲的消息：打包 -> 匹配记忆 -> 调用API -> 发送回复"""
    with buffer_lock:
        if user_id not in user_message_buffer or not user_message_buffer[user_id]:
            if user_id in user_timers:
                del user_timers[user_id]
            return
        
        packed_message = "\n".join(user_message_buffer[user_id])
        user_message_buffer[user_id] = []
        if user_id in user_timers:
            del user_timers[user_id]
    
    try:
        with buffer_lock:
            user_message_count[user_id] = user_message_count.get(user_id, 0) + 1
            current_count = user_message_count[user_id]
        
        keywords = extract_keywords(packed_message)
        memory = get_user_memory(user_id)
        matched_memories = memory.match_keywords(keywords)
        extra_context = ""
        if matched_memories:
            extra_context = matched_memories[0][1]
        
        assistant_reply = call_llm_api(user_id, packed_message, extra_context)
        if not assistant_reply:
            print(f"[Telegram] 用户{user_id}调用API失败：{packed_message}")
            logging.error(f"[Telegram] 用户{user_id}调用API失败：{packed_message}")
            return
        print(f"[Telegram] 用户{user_id}打包消息：{packed_message}")
        logging.info(f"[Telegram] 用户{user_id}打包消息：{packed_message}")
        print(f"[Telegram] 用户{user_id}打包消息：{packed_message}")
        logging.info(f"[Telegram] AI原始回复：{assistant_reply}")

        update_triggered = (8 <= current_count <= 12) and (current_count % random.randint(1, 3) == 0)
        high_importance_keywords = {"生病", "离职", "生日", "恋爱", "考试", "旅行"}
        if not update_triggered and any(kw in packed_message for kw in high_importance_keywords):
            update_triggered = True
        
        if update_triggered:
            new_memories = extract_new_memories(user_id)
            if new_memories:
                memory.update_memories(new_memories)
                print(f"[Telegram] 用户{user_id}新增{len(new_memories)}条记忆")
                logging.info(f"[记忆更新] 用户{user_id}新增{len(new_memories)}条记忆")
            with buffer_lock:
                user_message_count[user_id] = 0

        # Split by $ first, then by newlines to handle cases where AI uses \n instead of $
        raw_segments = assistant_reply.split('$')
        reply_segments = []
        for seg in raw_segments:
            lines = [line.strip() for line in seg.split('\n') if line.strip()]
            reply_segments.extend(lines)
            
        if not reply_segments:
            reply_segments = [assistant_reply.strip()]

        for idx, segment in enumerate(reply_segments):
            if not segment:
                continue
            
            base_delay = 2 if idx == 0 else 0.5
            char_delay = 2 / 10
            total_delay = base_delay + len(segment) * char_delay
            total_delay = max(min(total_delay + random.uniform(-1, 1), 10), 1)
            
            time.sleep(total_delay)
            if safe_send_message(user_id, segment):
                print(f"[Telegram] 发第{idx+1}段（延时{total_delay:.2f}秒）：{segment}")
                logging.info(f"[Telegram] 发第{idx+1}段（延时{total_delay:.2f}秒）：{segment}")
            else:
                print(f"[Telegram] 发第{idx+1}段失败：{segment}")
                logging.warning(f"[Telegram] 发第{idx+1}段失败：{segment}")
    
    except Exception as e:
        error_msg = f"❌ 处理出错：{str(e)}"
        safe_send_message(user_id, error_msg)
        print(f"[Telegram] 失败：{error_msg}")
        logging.error(f"[Telegram] 失败：{error_msg}")

def add_user_message(user_id, message_text):
    """添加用户消息到缓冲区，并管理计时器"""
    with buffer_lock:
        if user_id not in user_message_buffer:
            user_message_buffer[user_id] = []
        
        user_message_buffer[user_id].append(message_text)
        print(f"[Telegram] 用户{user_id}新增消息：{message_text} | 当前缓冲数：{len(user_message_buffer[user_id])}")
        logging.info(f"[Telegram] 用户{user_id}新增消息：{message_text} | 当前缓冲数：{len(user_message_buffer[user_id])}")
        
        collect_time = random.uniform(
            system_config.message_buffer.collect_min_time, 
            system_config.message_buffer.collect_max_time
        )
        
        if user_id in user_timers:
            existing_timer = user_timers[user_id]
            existing_timer.cancel()
        
        timer = threading.Timer(collect_time, process_user_messages, args=[user_id])
        timer.daemon = True
        timer.start()
        
        user_timers[user_id] = timer
        print(f"[Telegram] 用户{user_id}启动/重置计时器，将在{collect_time:.1f}秒后处理消息")
        logging.info(f"[Telegram] 用户{user_id}启动/重置计时器，将在{collect_time:.1f}秒后处理消息")

# ====================== Telegram消息处理器 ======================
@tb_bot.message_handler(func=lambda msg: msg.text.strip() == "/help")
def handle_help(message):
    help_text = (
        "📖 可用命令：\n"
        "/start_aiGF - 开启ai女友对话模式\n"
        "/stop_aiGF - 关闭ai女友对话模式\n"
        "/set_private [true|false] - 设置机器人是否仅对Owner可用\n"
        "/help - 显示此帮助信息"
    )
    tb_bot.reply_to(message, help_text)
    print(f"[Telegram] 用户 {message.from_user.id} 请求帮助")
    logging.info(f"[Telegram] 用户 {message.from_user.id} 请求帮助")

@tb_bot.message_handler(func=lambda msg: msg.text.strip().startswith("/set_private"))
def handle_set_private(message):
    global bot_is_private
    user_id = message.from_user.id
    if user_id != OWNER_ID:
        # 权限不足，直接忽略或拒绝
        return 
    
    parts = message.text.strip().split()
    if len(parts) != 2:
        tb_bot.reply_to(message, "Usage: /set_private [true|false]")
        return
        
    arg = parts[1].lower()
    if arg == "true":
        bot_is_private = True
        tb_bot.reply_to(message, "🔒 Bot is now in PRIVATE mode.")
        logging.info(f"[Telegram] Owner {user_id} enabled PRIVATE mode.")
    elif arg == "false":
        bot_is_private = False
        tb_bot.reply_to(message, "🔓 Bot is now in PUBLIC mode.")
        logging.info(f"[Telegram] Owner {user_id} enabled PUBLIC mode.")
    else:
        tb_bot.reply_to(message, "Usage: /set_private [true|false]")

@tb_bot.message_handler(func=lambda msg: msg.text.strip() == "/start_aiGF")
def handle_start_ai_chat(message):
    global ai_chat_active
    user_id = message.from_user.id
    
    if bot_is_private and user_id != OWNER_ID:
        tb_bot.reply_to(message, "🔒 机器人当前处于私有模式，仅管理员可用。")
        return
        
    with chat_lock:
        ai_chat_active.add(user_id)
    
    get_user_memory(user_id)
    generate_user_prompt(user_id)
    with buffer_lock:
        user_message_count[user_id] = 0
    
    # 启动主动消息循环
    proactive_scheduler.start(user_id)

    tb_bot.reply_to(message, "✅ ai女友对话已开启！现在可以直接发送消息获取回复，输入/stop_aiGF关闭该模式。")
    print(f"[Telegram] 用户 {user_id} 开启了DeepSeek对话模式")
    logging.info(f"[Telegram] 用户 {user_id} 开启了DeepSeek对话模式")

@tb_bot.message_handler(func=lambda msg: msg.text.strip() == "/stop_aiGF")
def handle_stop_ai_chat(message):
    global ai_chat_active
    user_id = message.from_user.id
    
    with chat_lock:
        ai_chat_active.discard(user_id)
    
    with buffer_lock:
        if user_id in user_message_buffer:
            del user_message_buffer[user_id]
        if user_id in user_timers:
            user_timers[user_id].cancel()
            del user_timers[user_id]
        if user_id in user_message_count:
            del user_message_count[user_id]
    
    with context_lock:
        if user_id in chat_context:
            del chat_context[user_id]
    if user_id in user_prompt_cache:
        del user_prompt_cache[user_id]
    
    # 停止主动消息循环
    proactive_scheduler.stop(user_id)

    tb_bot.reply_to(message, "❌ ai女友对话模式已关闭！")
    print(f"[Telegram] 用户 {user_id} 关闭了ai女友对话模式")
    logging.info(f"[Telegram] 用户 {user_id} 关闭了ai女友对话模式")

@tb_bot.message_handler(func=lambda msg: msg.text.strip().startswith("/weather"))
def handle_weather(message):
    try:
        args = message.text.strip().split()
        if len(args) < 2:
            tb_bot.reply_to(message, "⚠️ 请输入城市名称，例如：/weather Beijing")
            return
        
        city = args[1]
        registry = APIRegistry()
        weather_api = registry.get_api("weather")
        
        if weather_api:
            result = weather_api.get_data(city)
            tb_bot.reply_to(message, f"🌦️ {result}")
        else:
            tb_bot.reply_to(message, "⚠️ 天气服务未启用或不可用。")
    except Exception as e:
        tb_bot.reply_to(message, f"❌ 获取天气失败：{str(e)}")

@tb_bot.message_handler(func=lambda msg: True)
def handle_ai_chat(message):
    if message.text.strip().startswith(('/start_aiGF', '/stop_aiGF', '/set_private','/help')):
        return
    
    user_id = message.from_user.id
    
    # 私有模式检查（防止聊天中途切换模式）
    if bot_is_private and user_id != OWNER_ID:
        # 如果用户之前在活跃列表里，现在被踢出去了
        with chat_lock:
            if user_id in ai_chat_active:
                ai_chat_active.discard(user_id)
                proactive_scheduler.stop(user_id)
                tb_bot.reply_to(message, "🔒 机器人已切换至私有模式，您的会话已结束。")
        return

    with chat_lock:
        if user_id not in ai_chat_active:
            return
    
    user_input = message.text.strip()
    
    # telegram无法发送空白消息 所以好像有没有无所谓
    if not user_input:
        tb_bot.reply_to(message, "⚠️ 消息内容不能为空，请重新输入！")
        return
    
    # 用户活跃，重置主动消息计时器
    proactive_scheduler.on_user_activity(user_id)

    add_user_message(user_id, user_input)

# ====================== Telegram轮询线程 ======================
def start_telegram_polling():
    print("[Telegram] 机器人轮询已启动，等待消息")
    logging.info("[Telegram] 机器人轮询已启动，等待消息")
    backoff = 1
    while True:
        try:
            tb_bot.polling(none_stop=True, timeout=90, long_polling_timeout=60)
            backoff = 1
        except requests.exceptions.ReadTimeout:
            continue
        except requests.exceptions.ConnectionError as e:
            print(f"[Telegram] 轮询连接异常：{str(e)}")
            logging.error(f"[Telegram] 轮询连接异常：{str(e)}")
        except Exception as e:
            print(f"[Telegram] 轮询异常：{str(e)}")
            logging.error(f"[Telegram] 轮询异常：{str(e)}")
        time.sleep(backoff)
        backoff = min(backoff * 2, 60)

# ====================== NoneBot启动配置 ======================
@driver.on_startup
async def startup():
    polling_thread = threading.Thread(target=start_telegram_polling, daemon=True)
    polling_thread.start()

# ====================== 运行NoneBot ======================
if __name__ == "__main__":
    nonebot.run()
