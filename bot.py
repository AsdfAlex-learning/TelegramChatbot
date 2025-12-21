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
    # 1. 拼接JSON文件路径（兼容不同操作系统）
    config_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config")
    json_path = os.path.join(config_dir, "Personality_Setting.json")
    
    # 2. 检查文件是否存在
    if not os.path.exists(json_path):
        raise FileNotFoundError(f"个性设置文件不存在：{json_path}，请检查路径是否正确")
    
    # 3. 读取并解析JSON
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            setting = json.load(f)
        # 4. 提取系统提示词（兜底：如果键不存在，返回默认值）
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
        # 添加当前用户输入
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
        return result["choices"][0]["message"]["content"].strip()

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
    with chat_lock:
        deepseek_chat_active = False
    tb_bot.reply_to(message, "❌ ai女友对话模式已关闭！")
    print(f"[Telegram] 用户 {message.from_user.id} 关闭了ai女友对话模式")

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
    
    # 调用DeepSeek API并回复
    user_input = message.text.strip()
    if not user_input:
        tb_bot.reply_to(message, "⚠️ 消息内容不能为空，请重新输入！")
        return
    
    try:
        # 1. 调用API获取带$分隔的回复
        deepseek_reply = call_deepseek_api(message.from_user.id, user_input)
        print(f"[Telegram] AI原始回复：{deepseek_reply}")  # 调试用：查看AI是否正确加了$

        # 2. 拆分回复：按$分割 + 过滤空字符串
        reply_segments = [seg.strip() for seg in deepseek_reply.split('$') if seg.strip()]
        # 兜底：如果AI没加$，则作为单段
        if not reply_segments:
            reply_segments = [deepseek_reply.strip()]

        # 3. 逐段发送（核心：只发拆分后的分段，不要重复发完整回复）
        for idx, segment in enumerate(reply_segments):
            if not segment:
                continue
            
            # 计算延时（修复波动范围）
            base_delay = 2 if idx == 0 else 0.5  # 第一条基础2秒，后续0.5秒
            char_delay = 2 / 10  # 每10字符加2秒
            total_delay = base_delay + len(segment) * char_delay
            total_delay += random.uniform(-1, 1)  # 缩小波动范围（±1秒，避免跳变）
            total_delay = max(min(total_delay, 10), 1)  # 限制1~10秒
            
            # 执行延时
            time.sleep(total_delay)
            
            # 发送当前分段（只发这一段，不要发完整deepseek_reply）
            tb_bot.send_message(message.from_user.id, segment)
            print(f"[Telegram] 发第{idx+1}段（延时{total_delay:.2f}秒）：{segment}")

    except Exception as e:
        error_msg = f"❌ 处理出错：{str(e)}"
        tb_bot.reply_to(message, error_msg)
        print(f"[Telegram] 失败：{error_msg}")
        
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

# 保留NoneBot原生echo命令（备用）
echo = on_command("echo", block=True)
@echo.handle()
async def handle_echo_nonebot(args: Message = CommandArg()):
    content = args.extract_plain_text()
    await echo.finish(content)




# ====================== 运行NoneBot ======================
if __name__ == "__main__":
    nonebot.run()