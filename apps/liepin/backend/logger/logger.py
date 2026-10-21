"""
----------------------------------------------------
 File Name:        Logger
 Author:           hoges
 Created Date:     2025/9/22
 Last Modified:    2025/9/22
 Python Version:   
----------------------------------------------------
"""
import os
import sys
import logging
import logging.config
import yaml
from datetime import datetime

_logger = None

def get_logger(name: str = "app"):
    global _logger
    if _logger is None:
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.join(BASE_DIR, "config", "logging.yaml")

        # 加载 YAML 配置
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f.read())

        if getattr(sys, "frozen", False):
            # 例如：打包后写到程序目录下的 logs_packed/
            log_base_dir = os.path.join(os.path.dirname(sys.executable))
        else:
            # 开发环境：项目根目录 logs/
            log_base_dir = os.path.join(BASE_DIR)

        os.makedirs(log_base_dir, exist_ok=True)

        # 动态生成带时间戳的日志文件名
        timestamp = datetime.now().strftime("_%Y-%m-%d_%H-%M-%S.log")
        for handler in config.get("handlers", {}).values():
            if "filename" in handler:
                original_path = handler["filename"]
                if not os.path.isabs(original_path):
                    original_path = os.path.join(log_base_dir, original_path)
                base, ext = os.path.splitext(original_path)
                if ext == "":
                    ext = ".log"
                new_path = f"{base}{timestamp}"
                if not new_path.endswith(".log"):
                    new_path += ".log"
                handler["filename"] = new_path
                os.makedirs(os.path.dirname(new_path), exist_ok=True)

        # 如果在打包的无控制台环境（例如 PyInstaller --noconsole）下，
        # sys.stdout 可能为 None。此时移除 console handler，避免 uvicorn/colored 输出尝试访问 None.isatty
        if getattr(sys, "frozen", False) and (getattr(sys, "stdout", None) is None or not hasattr(sys.stdout, "isatty") or sys.stdout is None):
            # 从配置中移除名为 console 的 handler，并在 root 与其他 logger 中移除引用
            handlers_cfg = config.get("handlers", {})
            if "console" in handlers_cfg:
                handlers_cfg.pop("console", None)

            # 移除 top-level root handlers 中的 console 引用
            root_cfg = config.get("root")
            if isinstance(root_cfg, dict):
                handlers = root_cfg.get("handlers")
                if isinstance(handlers, list) and "console" in handlers:
                    root_cfg["handlers"] = [h for h in handlers if h != "console"]

            # 移除 loggers 每个子 logger 中的 console 引用
            loggers_cfg = config.get("loggers", {})
            if isinstance(loggers_cfg, dict):
                for lname, lcfg in loggers_cfg.items():
                    if isinstance(lcfg, dict):
                        handlers = lcfg.get("handlers")
                        if isinstance(handlers, list) and "console" in handlers:
                            lcfg["handlers"] = [h for h in handlers if h != "console"]

        # 自动创建日志目录
        for handler in config.get("handlers", {}).values():
            if "filename" in handler:
                log_file_path = handler["filename"]
                if not os.path.isabs(log_file_path):
                    log_file_path = os.path.join(BASE_DIR, log_file_path)
                    handler["filename"] = log_file_path
                os.makedirs(os.path.dirname(log_file_path), exist_ok=True)

        logging.config.dictConfig(config)
        _logger = logging.getLogger(name)

    return _logger

