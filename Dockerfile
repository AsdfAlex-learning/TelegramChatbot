# 使用官方 Python 轻量级镜像
FROM python:3.10-slim

# 设置环境变量
# PYTHONUNBUFFERED=1: 防止 Python 缓冲标准输出/错误输出，保证日志实时打印
# PYTHONDONTWRITEBYTECODE=1: 防止生成 .pyc 文件
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# 设置工作目录
WORKDIR /app

# 复制依赖文件并安装
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目所有文件
COPY . .

# 暴露端口 (NoneBot 默认通常是 8080)
EXPOSE 8080

# 启动命令
CMD ["python", "run.py"]
