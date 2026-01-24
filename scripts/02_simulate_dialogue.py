import os
import sys
import argparse
import mlflow
import json
import time
from typing import List, Dict
from openai import OpenAI
from pathlib import Path

# 添加项目根目录到 sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

def simulate_conversation(
    client_local: OpenAI, 
    client_simulator: OpenAI, 
    simulator_model: str, 
    local_model: str,
    topics: List[str],
    turns: int = 5
):
    """
    模拟对话过程
    """
    dialogue_data = []

    for topic in topics:
        print(f"--- 开始模拟话题: {topic} ---")
        
        # 模拟器的 System Prompt
        simulator_system_prompt = f"""
        你是一个好奇的用户，正在与一个 AI 助手进行对话。
        当前的话题是：{topic}。
        请提出相关问题，并根据 AI 的回答进行追问。
        请保持对话自然，每次只说一句话。
        """
        
        # 本地模型的 System Prompt (假设在 server 端配置，或者通过 API 传递)
        local_system_prompt = "你是一个乐于助人的 AI 助手。"
        
        history_local = [{"role": "system", "content": local_system_prompt}]
        history_simulator = [{"role": "system", "content": simulator_system_prompt}]
        
        # 模拟器先发起话题
        simulator_response = client_simulator.chat.completions.create(
            model=simulator_model,
            messages=history_simulator
        )
        user_input = simulator_response.choices[0].message.content
        print(f"User (Sim): {user_input}")
        
        history_simulator.append({"role": "assistant", "content": user_input}) # 模拟器认为自己是 assistant (实际是 user 角色)
        history_local.append({"role": "user", "content": user_input})
        
        current_dialogue = {
            "topic": topic,
            "turns": []
        }
        
        for _ in range(turns):
            # 1. 本地模型生成回答
            start_time = time.time()
            try:
                local_response = client_local.chat.completions.create(
                    model=local_model,
                    messages=history_local
                )
                assistant_output = local_response.choices[0].message.content
            except Exception as e:
                print(f"Local Model Error: {e}")
                break
            latency = time.time() - start_time
            print(f"AI (Local): {assistant_output}")
            
            history_local.append({"role": "assistant", "content": assistant_output})
            history_simulator.append({"role": "user", "content": assistant_output})
            
            # 记录这一轮
            current_dialogue["turns"].append({
                "user": user_input,
                "assistant": assistant_output,
                "latency": latency
            })
            
            # 2. 模拟器生成下一句追问
            try:
                simulator_response = client_simulator.chat.completions.create(
                    model=simulator_model,
                    messages=history_simulator
                )
                user_input = simulator_response.choices[0].message.content
            except Exception as e:
                print(f"Simulator Error: {e}")
                break
                
            print(f"User (Sim): {user_input}")
            
            history_simulator.append({"role": "assistant", "content": user_input})
            history_local.append({"role": "user", "content": user_input})
            
        dialogue_data.append(current_dialogue)
        
    return dialogue_data

if __name__ == "__main__":
    # 加载系统配置
    config_loader = ConfigLoader()
    llm_config = config_loader.system_config.llm
    
    default_api_key = llm_config.api_key
    default_api_base = get_clean_api_base(llm_config.api_url)
    default_model = llm_config.model

    parser = argparse.ArgumentParser(description="模拟对话并记录到 MLflow")
    parser.add_argument("--local_api_base", type=str, default="http://localhost:8000/v1", help="本地模型 API 地址")
    parser.add_argument("--local_api_key", type=str, default="sk-dummy", help="本地模型 API Key")
    parser.add_argument("--simulator_api_base", type=str, default=default_api_base, help="模拟器 API 地址 (默认从 config 读取)")
    parser.add_argument("--simulator_api_key", type=str, default=default_api_key, help="模拟器 API Key (默认从 config 读取)")
    parser.add_argument("--simulator_model", type=str, default=default_model, help="模拟器模型名称 (默认从 config 读取)")
    parser.add_argument("--local_model", type=str, default="local-model", help="本地模型名称")
    parser.add_argument("--output_file", type=str, default="simulation_data.json", help="输出文件路径")
    parser.add_argument("--experiment_name", type=str, default="LLM_Bootstrap", help="MLflow 实验名称")

    args = parser.parse_args()
    
    # 初始化客户端
    client_local = OpenAI(base_url=args.local_api_base, api_key=args.local_api_key)
    client_simulator = OpenAI(base_url=args.simulator_api_base, api_key=args.simulator_api_key)
    
    # 模拟话题
    topics = [
        "Python 编程中的装饰器",
        "如何制作红烧肉",
        "解释量子纠缠",
        "推荐几本好看的科幻小说"
    ]
    
    mlflow.set_experiment(args.experiment_name)
    with mlflow.start_run(run_name="simulate_dialogue") as run:
        data = simulate_conversation(
            client_local, 
            client_simulator, 
            args.simulator_model, 
            args.local_model, 
            topics
        )
        
        # 保存数据
        with open(args.output_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
        # 记录 artifact
        mlflow.log_artifact(args.output_file)
        print(f"对话模拟完成，数据已保存至 {args.output_file} 并上传至 MLflow Run {run.info.run_id}")
