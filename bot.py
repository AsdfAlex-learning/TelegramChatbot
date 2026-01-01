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
from memory import LongTermMemory


nonebot.init(env_file=".env.prod")
driver = get_driver()

def load_secrets():
    secrets_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config", "PROTECTED_INFO.json")
    with open(secrets_path, "r", encoding="utf-8") as f:
        return json.load(f)

def load_personality_setting():
    config_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config")
    json_path = os.path.join(config_dir, "Personality_Setting.json")
    if not os.path.exists(json_path):
        raise FileNotFoundError(f"个性设置文件不存在：{json_path}，请检查路径是否正确")
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            setting = json.load(f)
        system_prompt = setting.get("system_prompt", "")
        if not system_prompt:
            raise ValueError("JSON文件中未找到system_prompt字段，或字段值为空")
        return system_prompt
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON文件格式错误：{str(e)}，请检查语法是否正确")

secrets = load_secrets()
TELEGRAM_TOKEN = secrets["TELEGRAM_TOKEN"]
DEEPSEEK_API_KEY = secrets["DEEPSEEK_API_KEY"]
DEEPSEEK_API_URL = secrets["DEEPSEEK_API_URL"]
BASE_SYSTEM_PROMPT = load_personality_setting()
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

# ========== 长期记忆模块 ==========
# LongTermMemory 类已移动至 memory.py

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
            # 首次对话：加载系统提示词（包含USER_PROMPT）
            user_prompt = generate_user_prompt(user_id)
            full_system_prompt = f"{BASE_SYSTEM_PROMPT}\n\n{user_prompt}"
            chat_context[user_id] = [{"role": "system", "content": full_system_prompt.strip()}]
        else:
            # 已存在上下文：检查是否需要添加额外记忆
            if extra_context:
                chat_context[user_id].append({"role": "system", "content": f"相关记忆：{extra_context}"})
        
        # 添加当前用户输入
        chat_context[user_id].append({"role": "user", "content": prompt})
        
        # 限制上下文长度（1条系统提示 + 10轮问答）
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
    # 检查缓存（24小时内有效）
    if user_id in user_prompt_cache:
        prompt, cache_time = user_prompt_cache[user_id]
        if time.time() - cache_time < 86400:
            return prompt
    
    # 无缓存时调用API生成
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
        recent_dialogs = chat_context[user_id][-20:]  # 最近10轮
    
    dialog_text = "\n".join([f"{d['role']}: {d['content']}" for d in recent_dialogs])
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": """从对话中提取用户的重要信息，按格式返回：
事件（YYYY-MM-DD + 具体事件）,关键词（逗号分隔）,重要度(0-100),有效期（天，365=永久）
仅保留重要信息，普通闲聊忽略。"""},
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
        # 更新对话轮数
        with buffer_lock:
            user_message_count[user_id] = user_message_count.get(user_id, 0) + 1
            current_count = user_message_count[user_id]
        
        # 关键词提取与记忆匹配
        keywords = extract_keywords(packed_message)
        memory = get_user_memory(user_id)
        matched_memories = memory.match_keywords(keywords)
        extra_context = ""
        if matched_memories:
            extra_context = matched_memories[0][1]  # 取第一条匹配的事件
        
        # 调用API获取回复
        deepseek_reply = call_deepseek_api(user_id, packed_message, extra_context)
        print(f"[Telegram] 用户{user_id}打包消息：{packed_message}")
        print(f"[Telegram] AI原始回复：{deepseek_reply}")

        # 检查是否需要更新记忆
        update_triggered = (8 <= current_count <= 12) and (current_count % random.randint(1, 3) == 0)
        high_importance_keywords = {"生病", "离职", "生日", "恋爱", "考试", "旅行"}
        if not update_triggered and any(kw in packed_message for kw in high_importance_keywords):
            update_triggered = True
        
        if update_triggered:
            new_memories = extract_new_memories(user_id)
            if new_memories:
                memory.update_memories(new_memories)
                print(f"[记忆更新] 用户{user_id}新增{len(new_memories)}条记忆")
            # 重置计数
            with buffer_lock:
                user_message_count[user_id] = 0

        # 拆分回复并发送
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
            tb_bot.send_message(user_id, segment)
            print(f"[Telegram] 发第{idx+1}段（延时{total_delay:.2f}秒）：{segment}")
    
    except Exception as e:
        error_msg = f"❌ 处理出错：{str(e)}"
        tb_bot.send_message(user_id, error_msg)
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
        deepseek_chat_active = True
    
    # 初始化用户记忆
    get_user_memory(user_id)
    # 生成初始USER_PROMPT
    generate_user_prompt(user_id)
    # 重置对话计数
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
    
    # 清空短期数据
    with buffer_lock:
        if user_id in user_message_buffer:
            del user_message_buffer[user_id]
        if user_id in user_timers:
            user_timers[user_id].cancel()
            del user_timers[user_id]
        if user_id in user_message_count:
            del user_message_count[user_id]
    
    # 清空上下文和缓存
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
    
    with chat_lock:
        if not deepseek_chat_active:
            return
    
    user_input = message.text.strip()
    user_id = message.from_user.id
    
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
    try:
        tb_bot.polling(none_stop=True, timeout=60)
    except Exception as e:
        print(f"[Telegram] 轮询异常：{str(e)}")

# ====================== NoneBot启动配置 ======================
@driver.on_startup
async def startup():
    polling_thread = threading.Thread(target=start_telegram_polling, daemon=True)
    polling_thread.start()

# ====================== 运行NoneBot ======================
if __name__ == "__main__":
    nonebot.run()