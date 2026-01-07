import os
import sys
import logging
from logging.handlers import TimedRotatingFileHandler


def setup_logging():
    project_root = os.path.dirname(os.path.abspath(__file__))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    log_dir = os.path.join(project_root, "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "bot_log.txt")

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    if not any(isinstance(h, TimedRotatingFileHandler) and getattr(h, "baseFilename", "") == os.path.abspath(log_file) for h in logger.handlers):
        file_handler = TimedRotatingFileHandler(
            log_file,
            when="midnight",
            interval=1,
            backupCount=0,
            encoding="utf-8",
        )
        file_handler.suffix = "%Y-%m-%d.txt"
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        logger.addHandler(console_handler)


def main():
    setup_logging()
    logging.info("程序启动")
    try:
        from src.bot.main import nonebot
        nonebot.run()
    except Exception:
        logging.exception("运行过程中出现未捕获异常")
        raise


if __name__ == "__main__":
    main()


