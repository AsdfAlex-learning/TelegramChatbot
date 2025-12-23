import nonebot
import os
import threading
import telebot
import requests
import time
import random
import json
import sys
from nonebot import on_command
from nonebot.adapters import Message
from nonebot.params import CommandArg
from nonebot import get_driver


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
SYSTEM_PROMPT = load_personality_setting()
deepseek_chat_active = False  # 控制对话模式开关
chat_lock = threading.Lock()  # 线程锁保证状态安全
chat_context = {}  # 格式：{user_id: [{"role": "...", "content": "..."}]}
context_lock = threading.Lock()  # 上下文操作的线程锁
user_memory = {}  

# ========== 消息缓冲相关配置 ==========
# 用户消息缓冲区 {user_id: [msg1, msg2, ...]}
user_message_buffer = {}
# 用户计时器存储 {user_id: timer_thread}
user_timers = {}
# 缓冲区操作锁
buffer_lock = threading.Lock()
# 消息收集时间范围（秒）
COLLECT_MIN_TIME = 15
COLLECT_MAX_TIME = 30

# 初始化Telegram机器人
tb_bot = telebot.TeleBot(TELEGRAM_TOKEN)

# ====================== DeepSeek API调用函数 ======================
def call_deepseek_api(user_id: int, prompt: str) -> str:
    """调用DeepSeek官方API获取回复"""
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    with context_lock:
        if user_id not in chat_context:
            # 首次对话：先添加系统提示词
            chat_context[user_id] = [{"role": "system", "content": SYSTEM_PROMPT.strip()}]
        # 添加当前用户输入（已打包的完整消息）
        chat_context[user_id].append({"role": "user", "content": prompt})
        
        # 可选：限制上下文长度（避免token超限），保留最近10轮对话
        if len(chat_context[user_id]) > 21:  # 1条系统提示 + 10轮问答（20条）
            chat_context[user_id] = [chat_context[user_id][0]] + chat_context[user_id][-20:]

    data = {
        "model": "deepseek-chat",  # DeepSeek默认模型
        "messages": chat_context[user_id],
        "temperature": 0.7,  # 回复随机性，0-1之间
        "max_tokens": 2048   # 最大回复长度
    }
    
    try:
        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=data, timeout=30)
        response.raise_for_status()  # 抛出HTTP错误
        result = response.json()
        assistant_reply = result["choices"][0]["message"]["content"].strip()

        with context_lock:
            chat_context[user_id].append({"role": "assistant", "content": assistant_reply})
            # 再次检查长度（避免加了回复后超限）
            if len(chat_context[user_id]) > 21:
                chat_context[user_id] = [chat_context[user_id][0]] + chat_context[user_id][-20:]
        
        return assistant_reply
    
    except requests.exceptions.RequestException as e:
        return f"API调用失败：{str(e)}"
    except KeyError as e:
        return f"API返回格式异常：缺少字段 {str(e)}"

# ========== 消息打包与发送核心函数 ==========
def process_user_messages(user_id):
    """处理用户缓冲的消息：打包 -> 调用API -> 发送回复"""
    with buffer_lock:
        # 1. 获取并清空用户缓冲区
        if user_id not in user_message_buffer or not user_message_buffer[user_id]:
            # 清除该用户的计时器记录
            if user_id in user_timers:
                del user_timers[user_id]
            return
        
        # 打包消息（用换行分隔碎片化消息）
        packed_message = "\n".join(user_message_buffer[user_id])
        # 清空缓冲区
        user_message_buffer[user_id] = []
        # 清除计时器记录
        if user_id in user_timers:
            del user_timers[user_id]
    
    try:
        # 2. 调用DeepSeek API获取回复
        deepseek_reply = call_deepseek_api(user_id, packed_message)
        print(f"[Telegram] 用户{user_id}打包消息：{packed_message}")
        print(f"[Telegram] AI原始回复：{deepseek_reply}")

        # 3. 拆分回复并逐段发送
        reply_segments = [seg.strip() for seg in deepseek_reply.split('$') if seg.strip()]
        if not reply_segments:
            reply_segments = [deepseek_reply.strip()]

        for idx, segment in enumerate(reply_segments):
            if not segment:
                continue
            
            # 计算发送延时
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
        # 初始化用户缓冲区
        if user_id not in user_message_buffer:
            user_message_buffer[user_id] = []
        
        # 添加消息到缓冲区
        user_message_buffer[user_id].append(message_text)
        print(f"[Telegram] 用户{user_id}新增消息：{message_text} | 当前缓冲数：{len(user_message_buffer[user_id])}")
        
        # 4. 管理计时器：如果已有计时器则重置，没有则创建
        # 随机生成收集时间（15-30秒）
        collect_time = random.uniform(COLLECT_MIN_TIME, COLLECT_MAX_TIME)
        
        if user_id in user_timers:
            # 取消现有计时器
            existing_timer = user_timers[user_id]
            existing_timer.cancel()
        
        # 创建新计时器
        timer = threading.Timer(collect_time, process_user_messages, args=[user_id])
        timer.daemon = True  # 设置为守护线程，不阻塞程序退出
        timer.start()
        
        # 保存新计时器
        user_timers[user_id] = timer
        print(f"[Telegram] 用户{user_id}启动/重置计时器，将在{collect_time:.1f}秒后处理消息")

# ====================== Telegram消息处理器 ======================
# 开启DeepSeek对话的命令（Telegram端）
@tb_bot.message_handler(func=lambda msg: msg.text.strip() == "/start_aiGF")
def handle_start_deepseek(message):
    global deepseek_chat_active
    with chat_lock:
        deepseek_chat_active = True
    tb_bot.reply_to(message, "✅ ai女友对话已开启！现在可以直接发送消息获取回复，输入/stop_aiGF关闭该模式。")
    print(f"[Telegram] 用户 {message.from_user.id} 开启了DeepSeek对话模式")

# 关闭DeepSeek对话的命令（Telegram端）
@tb_bot.message_handler(func=lambda msg: msg.text.strip() == "/stop_aiGF")
def handle_stop_deepseek(message):
    global deepseek_chat_active
    user_id = message.from_user.id
    
    # 关闭对话模式
    with chat_lock:
        deepseek_chat_active = False
    
    # 清空该用户的缓冲区和计时器
    with buffer_lock:
        if user_id in user_message_buffer:
            del user_message_buffer[user_id]
        if user_id in user_timers:
            user_timers[user_id].cancel()
            del user_timers[user_id]
    
    tb_bot.reply_to(message, "❌ ai女友对话模式已关闭！")
    print(f"[Telegram] 用户 {user_id} 关闭了ai女友对话模式")

# 核心：DeepSeek对话模式的消息处理（无触发词）
@tb_bot.message_handler(func=lambda msg: True)
def handle_deepseek_chat(message):
    # 跳过命令类消息（避免重复处理）
    if message.text.strip().startswith(('/start_aiGF', '/stop_aiGF')):
        return
    
    # 检查是否开启对话模式
    with chat_lock:
        if not deepseek_chat_active:
            return
    
    # 获取用户输入
    user_input = message.text.strip()
    user_id = message.from_user.id
    
    if not user_input:
        tb_bot.reply_to(message, "⚠️ 消息内容不能为空，请重新输入！")
        return
    
    # 添加消息到缓冲区并启动/重置计时器
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
# NoneBot启动时开启Telegram轮询线程
@driver.on_startup
async def startup():
    polling_thread = threading.Thread(target=start_telegram_polling, daemon=True)
    polling_thread.start()

# ====================== 运行NoneBot ======================
if __name__ == "__main__":
    nonebot.run()