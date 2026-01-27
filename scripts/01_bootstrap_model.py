import os
import sys
import argparse
import mlflow
import uvicorn
import threading
import time
import requests
from pathlib import Path

# 添加项目根目录到 sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.llm_system.monitor.mlflow_logger import MLflowLogger
from src.llm_system.monitor.ui_launcher import launch_mlflow_ui

def start_server(host: str, port: int, model_path: str, use_4bit: bool):
    """
    启动本地推理服务
    """
    # 设置环境变量供 app.py 使用
    os.environ["MODEL_PATH"] = model_path
    os.environ["USE_4BIT"] = str(use_4bit)
    
    # 导入 app (注意：这里需要在环境变量设置之后导入，或者修改 app.py 读取配置的方式)
    # 为了简单起见，假设 app.py 会在启动时读取环境变量或配置文件
    # 实际生产中建议使用配置文件
    
    # [TODO: Integration] Security & Skills Module Initialization
    # ------------------------------------------------------------
    # If the server needs to enforce security policies or use skills directly:
    # 
    # from src.security import SecurityPolicy
    # from src.skills import SkillRegistry
    # 
    # # Initialize global components
    # SecurityPolicy.load_from_file("config/security_policy.yaml")
    # SkillRegistry.load_skills("src/skills/definitions")
    # 
    # # Pass these to the app instance or set as global singletons
    # # app.state.security_policy = ...
    # ------------------------------------------------------------

    # 使用 uvicorn 启动
    # 注意：在代码中直接运行 uvicorn.run 会阻塞，所以通常放在主线程
    # 但这里我们需要同时做一些 MLflow 的记录，所以可以用子进程或直接作为入口
    
    print(f"正在启动推理服务... 模型: {model_path}")
    uvicorn.run("src.llm_system.server.app:app", host=host, port=port, reload=False)

def check_server_health(url: str, max_retries: int = 30):
    """
    检查服务是否启动成功
    """
    print("等待服务启动...")
    for i in range(max_retries):
        try:
            response = requests.get(f"{url}/docs")
            if response.status_code == 200:
                print("服务已启动！")
                return True
        except requests.RequestException:
            pass
        time.sleep(2)
    return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="启动模型并记录 MLflow 实验")
    parser.add_argument("--model_path", type=str, default="Qwen/Qwen2.5-3B-Instruct", help="模型路径或 HuggingFace ID")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="服务主机")
    parser.add_argument("--port", type=int, default=8000, help="服务端口")
    parser.add_argument("--use_4bit", action="store_true", default=True, help="使用 4-bit 量化")
    parser.add_argument("--experiment_name", type=str, default="LLM_Bootstrap", help="MLflow 实验名称")
    
    args = parser.parse_args()

    # 启动 MLflow UI
    launch_mlflow_ui()

    # 初始化 MLflow
    logger = MLflowLogger()
    mlflow.set_experiment(args.experiment_name)
    
    with mlflow.start_run(run_name="bootstrap_model") as run:
        # 记录参数
        mlflow.log_params({
            "model_path": args.model_path,
            "use_4bit": args.use_4bit,
            "host": args.host,
            "port": args.port
        })
        
        print(f"MLflow Run ID: {run.info.run_id}")
        
        # 启动服务
        # 实际操作中，这个脚本可能主要用于启动服务进程
        # 这里直接运行 uvicorn
        try:
            start_server(args.host, args.port, args.model_path, args.use_4bit)
        except KeyboardInterrupt:
            print("服务已停止")
