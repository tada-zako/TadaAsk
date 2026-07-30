import json
import logging
import sys
import threading
from datetime import UTC
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loguru import logger

if TYPE_CHECKING:
    from app.core.config import Settings


_CONSOLE_FORMAT = (
    "<green>{time:YYYY-MM-DDTHH:mm:ss.SSS!UTC}Z</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
    "<level>{message}</level>{extra[context]}\n{exception}"
)
# 常见的标准 logging 对象
_STANDARD_LOGGERS = (
    "alembic",
    "asyncio",
    "fastapi",
    "httpcore",
    "httpx",
    "sqlalchemy",
    "sqlalchemy.engine",
    "starlette",
    "uvicorn",
    "uvicorn.access",
    "uvicorn.error",
)
_configuration_lock = threading.Lock()
_configuration_signature: tuple[str, str, bool, str] | None = None


class InterceptHandler(logging.Handler):
    """拦截标准 logging 记录并转发到 Loguru 的 Handler。"""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            # 获取 loguru 对应的 level (如果村咋)
            level: str | int = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # 查找 logged message 的发起者
        frame = logging.currentframe()
        depth = 0
        # 跳过 logging 自身和当前桥接层栈帧，让 Loguru 指向原始调用位置。
        while frame and (depth == 0 or frame.f_code.co_filename == logging.__file__):
            frame = frame.f_back
            depth += 1

        logger.bind(logging_name=record.name).opt(
            depth=depth,  # 用于追溯 logging 原始触发位置
            exception=record.exc_info,
        ).log(level, record.getMessage())


def configure_logging(app_settings: "Settings") -> None:
    """配置应用与第三方库共用的 loguru 日志输出。"""
    global _configuration_signature

    signature = (
        app_settings.log_level,
        app_settings.log_format,
        app_settings.log_file_enabled,
        app_settings.log_file_path,
    )

    with _configuration_lock:
        if signature != _configuration_signature:
            if _configuration_signature is not None:
                # 当前只使用同步 sink；complete() 的同步阶段会先排空 enqueue 队列。
                logger.complete()

            handlers: list[dict[str, Any]] = [
                {
                    "sink": _write_console,
                    "level": app_settings.log_level,
                    "format": (
                        _console_format
                        if app_settings.log_format == "console"
                        else "{message}"
                    ),
                    "colorize": (
                        sys.stderr.isatty()
                        if app_settings.log_format == "console"
                        else False
                    ),
                    "serialize": app_settings.log_format == "json",
                    "enqueue": True,
                    "backtrace": True,
                    "diagnose": False,
                }
            ]

            if app_settings.log_file_enabled:
                log_file_path = Path(app_settings.log_file_path)
                log_file_path.parent.mkdir(parents=True, exist_ok=True)
                handlers.append(
                    {
                        "sink": log_file_path,
                        "level": app_settings.log_level,
                        "serialize": True,
                        "enqueue": True,
                        "backtrace": True,
                        "diagnose": False,
                        "encoding": "utf8",
                        "rotation": "15 MB",
                        "retention": "14 days",
                        "compression": "zip",
                    }
                )

            logger.configure(
                handlers=handlers,
                extra={"service": "tadaask-backend"},
                patcher=_use_utc_time,
            )
            _configuration_signature = signature

        # Alembic 或测试可能在两次调用之间重配标准 logging。
        # 每次都恢复桥接，但相同配置不会重复创建 Loguru sink。
        _configure_standard_logging(app_settings)


async def complete_logging() -> None:
    """等待队列和异步 sink 完成，避免应用退出时丢失尾部日志。"""
    await logger.complete()


def _configure_standard_logging(app_settings: "Settings") -> None:
    """为依赖库中的标准 logging 设置额外配置"""
    handler = InterceptHandler()
    root_logger = logging.getLogger()
    root_logger.handlers = [handler]  # 确保只有 InterceptHandler 生效
    root_logger.setLevel(_standard_level(app_settings.log_level))

    # 避免同一条记录同时由标准 logging 和 Loguru 输出。
    for logger_name in _STANDARD_LOGGERS:
        standard_logger = logging.getLogger(logger_name)
        # 移除标准 logging 可能安装的独立 handler，并向 root 传播 message。
        standard_logger.handlers.clear()
        standard_logger.propagate = True
        standard_logger.setLevel(logging.NOTSET)

    # 抬高标准 logging 默认输出级别以减少噪声和泄露。
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if app_settings.sqlalchemy_echo else logging.WARNING
    )
    logging.captureWarnings(True)


def _standard_level(level: str) -> int:
    if level == "TRACE":
        return 5
    if level == "SUCCESS":
        return logging.INFO
    return logging.getLevelNamesMapping()[level]


def _console_format(record: dict[str, Any]) -> str:
    # 将所有的 extra 上下文归一化为 context 进行输出，方便动态追加 extra。
    extra = record["extra"]
    context_parts = []
    for key in sorted(extra):
        if key == "context":
            continue
        value = json.dumps(extra[key], ensure_ascii=False, default=str)
        context_parts.append(f"{key}={value}")

    extra["context"] = f" | {' '.join(context_parts)}" if context_parts else ""
    return _CONSOLE_FORMAT


def _write_console(message: Any) -> None:
    # 运行时读取 sys.stderr，兼容测试捕获以及宿主进程替换输出流。
    sys.stderr.write(str(message))


def _use_utc_time(record: dict[str, Any]) -> None:
    record["time"] = record["time"].astimezone(UTC)
