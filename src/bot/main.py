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
from datetime import datetime, timedelta
from nonebot import on_command
from nonebot.adapters import Message
from nonebot.params import CommandArg
from nonebot import get_driver
from src.storage.memory import LongTermMemory


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

nonebot.init(env_file=os.path.join(PROJECT_ROOT, ".env.prod"))
driver = get_driver()

def load_config():
    config_path = os.path.join(PROJECT_ROOT, "config", "config.json")
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"配置文件不存在：{config_path}（可参考 config/example_config.json）")
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON文件格式错误：{str(e)}，请检查语法是否正确")

def load_persona_card(card_name: str, config: dict):
    default_name = "persona_setting"
    system_prompt_section = config.get("system_prompt", {}) if isinstance(config, dict) else {}
    default_persona = system_prompt_section.get("default_persona", "")

    if not card_name or card_name == default_name:
        return default_persona

    persona_section = config.get("persona_card", {}) if isinstance(config, dict) else {}
    cards = {}
    if isinstance(persona_section, dict):
        cards = persona_section.get("cards") if isinstance(persona_section.get("cards"), dict) else {}
        if not cards and all(isinstance(v, str) for v in persona_section.values()):
            cards = persona_section

    if card_name in cards and isinstance(cards[card_name], str):
        return cards[card_name]

    persona_dir = os.path.join(PROJECT_ROOT, "config", "persona_card")
    candidate_paths = [
        os.path.join(persona_dir, f"{card_name}.txt"),
        os.path.join(persona_dir, f"{card_name}.json"),
    ]
    for path in candidate_paths:
        if not os.path.exists(path):
            continue
        if path.endswith(".txt"):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
        if isinstance(obj, str):
            return obj
        if isinstance(obj, dict):
            for key in ("persona", "system_prompt", "content"):
                if isinstance(obj.get(key), str) and obj.get(key).strip():
                    return obj[key]
    raise FileNotFoundError(f"未找到人格卡片：{card_name}")

def build_base_system_prompt(config: dict):
    system_prompt_section = config.get("system_prompt", {}) if isinstance(config, dict) else {}
    core_rules = system_prompt_section.get("core_rules", "")
    persona_section = config.get("persona_card", {}) if isinstance(config, dict) else {}
    selected = "persona_setting"
    if isinstance(persona_section, dict):
        selected = persona_section.get("character_name") or persona_section.get("selected") or persona_section.get("name") or selected
    elif isinstance(persona_section, str):
        selected = persona_section
    persona_text = load_persona_card(str(selected), config)
    return "\n\n".join([str(core_rules).strip(), str(persona_text).strip()]).strip()

config = load_config()
TELEGRAM_TOKEN = config.get("telegram", {}).get("bot_token")
DEEPSEEK_API_KEY = config.get("deepseek", {}).get("api_key")
DEEPSEEK_API_URL = config.get("deepseek", {}).get("api_url")
BASE_SYSTEM_PROMPT = build_base_system_prompt(config)
if not TELEGRAM_TOKEN:
    raise ValueError("config/config.json 缺少 telegram.bot_token")
if not DEEPSEEK_API_KEY:
    raise ValueError("config/config.json 缺少 deepseek.api_key")
if not DEEPSEEK_API_URL:
    raise ValueError("config/config.json 缺少 deepseek.api_url")
deepseek_chat_active = set()  # 存储已开启AI对话的用户ID
chat_lock = threading.Lock()  # 线程锁保证状态安全
chat_context = {}  # 格式：{user_id: [{"role": "...", "content": "..."}]}
context_lock = threading.Lock()  # 上下文操作的线程锁
user_message_count = {}  # 记录对话轮数：{user_id: count}
user_prompt_cache = {}  # USER_PROMPT缓存：{user_id: (prompt, cache_time)}

# ========== 消息缓冲相关配置 ==========
user_message_buffer = {}  # {user_id: [msg1, msg2, ...]}
user_timers = {}  # {user_id: timer_thread}
buffer_lock = threading.Lock()
COLLECT_MIN_TIME = 15
COLLECT_MAX_TIME = 20

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
                return False
            time.sleep(backoff)
            backoff = min(backoff * 2, 10)
        except Exception as e:
            print(f"[Telegram] 发送异常（chat_id={chat_id}）：{e}")
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

# ====================== DeepSeek API调用函数 ======================
def call_deepseek_api(user_id: int, prompt: str, extra_context: str = "") -> str:
    """调用DeepSeek官方API获取回复，支持添加额外记忆上下文"""
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    with context_lock:
        if user_id not in chat_context:
            user_prompt = generate_user_prompt(user_id)
            full_system_prompt = f"{BASE_SYSTEM_PROMPT}\n\n{user_prompt}"
            chat_context[user_id] = [{"role": "system", "content": full_system_prompt.strip()}]
        else:
            if extra_context:
                chat_context[user_id].append({"role": "system", "content": f"相关记忆：{extra_context}"})
        
        chat_context[user_id].append({"role": "user", "content": prompt})
        
        if len(chat_context[user_id]) > 21:
            chat_context[user_id] = [chat_context[user_id][0]] + chat_context[user_id][-20:]

    data = {
        "model": "deepseek-chat",
        "messages": chat_context[user_id],
        "temperature": 0.7,
        "max_tokens": 2048
    }
    
    try:
        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=data, timeout=30)
        response.raise_for_status()
        result = response.json()
        assistant_reply = result["choices"][0]["message"]["content"].strip()

        with context_lock:
            chat_context[user_id].append({"role": "assistant", "content": assistant_reply})
            if len(chat_context[user_id]) > 21:
                chat_context[user_id] = [chat_context[user_id][0]] + chat_context[user_id][-20:]
        
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
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "根据以下用户记忆，生成≤200字的USER_PROMPT，分核心层（永久属性）和动态层（临时事件）。核心层必加，动态层仅在相关时提及。"},
            {"role": "user", "content": "\n".join(mem_descriptions)}
        ]
    }
    
    try:
        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=data, timeout=30)
        user_prompt = response.json()["choices"][0]["message"]["content"].strip()
        user_prompt_cache[user_id] = (user_prompt, time.time())
        return user_prompt
    except Exception as e:
        print(f"生成USER_PROMPT失败：{e}")
        return "用户信息加载中..."

def extract_keywords(text):
    """提取文本关键词（简化版，实际可优化）"""
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "提取输入文本的核心关键词，用逗号分隔，不超过5个词。"},
            {"role": "user", "content": text}
        ]
    }
    try:
        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=data, timeout=10)
        return response.json()["choices"][0]["message"]["content"].split(',')
    except:
        return text.split()[:5]

def extract_new_memories(user_id):
    """从最近对话中提取新记忆"""
    with context_lock:
        if user_id not in chat_context:
            return []
        recent_dialogs = chat_context[user_id][-20:]
    
    dialog_text = "\n".join([f"{d['role']}: {d['content']}" for d in recent_dialogs])
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "deepseek-chat",
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
        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=data, timeout=30)
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
        
        deepseek_reply = call_deepseek_api(user_id, packed_message, extra_context)
        print(f"[Telegram] 用户{user_id}打包消息：{packed_message}")
        print(f"[Telegram] AI原始回复：{deepseek_reply}")

        update_triggered = (8 <= current_count <= 12) and (current_count % random.randint(1, 3) == 0)
        high_importance_keywords = {"生病", "离职", "生日", "恋爱", "考试", "旅行"}
        if not update_triggered and any(kw in packed_message for kw in high_importance_keywords):
            update_triggered = True
        
        if update_triggered:
            new_memories = extract_new_memories(user_id)
            if new_memories:
                memory.update_memories(new_memories)
                print(f"[记忆更新] 用户{user_id}新增{len(new_memories)}条记忆")
            with buffer_lock:
                user_message_count[user_id] = 0

        reply_segments = [seg.strip() for seg in deepseek_reply.split('$') if seg.strip()]
        if not reply_segments:
            reply_segments = [deepseek_reply.strip()]

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
            else:
                print(f"[Telegram] 发第{idx+1}段失败：{segment}")
    
    except Exception as e:
        error_msg = f"❌ 处理出错：{str(e)}"
        safe_send_message(user_id, error_msg)
        print(f"[Telegram] 失败：{error_msg}")

def add_user_message(user_id, message_text):
    """添加用户消息到缓冲区，并管理计时器"""
    with buffer_lock:
        if user_id not in user_message_buffer:
            user_message_buffer[user_id] = []
        
        user_message_buffer[user_id].append(message_text)
        print(f"[Telegram] 用户{user_id}新增消息：{message_text} | 当前缓冲数：{len(user_message_buffer[user_id])}")
        
        collect_time = random.uniform(COLLECT_MIN_TIME, COLLECT_MAX_TIME)
        
        if user_id in user_timers:
            existing_timer = user_timers[user_id]
            existing_timer.cancel()
        
        timer = threading.Timer(collect_time, process_user_messages, args=[user_id])
        timer.daemon = True
        timer.start()
        
        user_timers[user_id] = timer
        print(f"[Telegram] 用户{user_id}启动/重置计时器，将在{collect_time:.1f}秒后处理消息")

# ====================== Telegram消息处理器 ======================
@tb_bot.message_handler(func=lambda msg: msg.text.strip() == "/start_aiGF")
def handle_start_deepseek(message):
    global deepseek_chat_active
    user_id = message.from_user.id
    
    with chat_lock:
        deepseek_chat_active.add(user_id)
    
    get_user_memory(user_id)
    generate_user_prompt(user_id)
    with buffer_lock:
        user_message_count[user_id] = 0
    
    tb_bot.reply_to(message, "✅ ai女友对话已开启！现在可以直接发送消息获取回复，输入/stop_aiGF关闭该模式。")
    print(f"[Telegram] 用户 {user_id} 开启了DeepSeek对话模式")

@tb_bot.message_handler(func=lambda msg: msg.text.strip() == "/stop_aiGF")
def handle_stop_deepseek(message):
    global deepseek_chat_active
    user_id = message.from_user.id
    
    with chat_lock:
        deepseek_chat_active.discard(user_id)
    
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
    
    tb_bot.reply_to(message, "❌ ai女友对话模式已关闭！")
    print(f"[Telegram] 用户 {user_id} 关闭了ai女友对话模式")

@tb_bot.message_handler(func=lambda msg: True)
def handle_deepseek_chat(message):
    if message.text.strip().startswith(('/start_aiGF', '/stop_aiGF')):
        return
    
    user_id = message.from_user.id
    with chat_lock:
        if user_id not in deepseek_chat_active:
            return
    
    user_input = message.text.strip()
    
    if not user_input:
        tb_bot.reply_to(message, "⚠️ 消息内容不能为空，请重新输入！")
        return
    
    add_user_message(user_id, user_input)

# ====================== Telegram轮询线程 ======================
def start_telegram_polling():
    print("[Telegram] 机器人轮询已启动，等待消息...")
    print("📌 可用命令：")
    print("   /start_aiGF - 开启ai对话模式")
    print("   /stop_aiGF  - 关闭ai对话模式")
    backoff = 1
    while True:
        try:
            tb_bot.polling(none_stop=True, timeout=90, long_polling_timeout=60)
            backoff = 1
        except requests.exceptions.ReadTimeout:
            continue
        except requests.exceptions.ConnectionError as e:
            print(f"[Telegram] 轮询连接异常：{str(e)}")
        except Exception as e:
            print(f"[Telegram] 轮询异常：{str(e)}")
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

