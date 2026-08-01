import json
import logging
import re
import sys
import threading
from datetime import UTC
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loguru import logger

if TYPE_CHECKING:
    from app.core.config import Settings


_CONSOLE_LEVEL_NAMES = {
    "TRACE": "TRCE",
    "DEBUG": "DEBG",
    "INFO": "INFO",
    "SUCCESS": "SUCC",
    "WARNING": "WARN",
    "ERROR": "ERRO",
    "CRITICAL": "CRIT",
}
_CONSOLE_FORMAT = (
    "<green>{local_time}</green> "
    "<level>[{level}]</level> "
    "<cyan>[{component}]</cyan> "
    "<level>{{message}}</level>{context}  "
    "<dim>{location}</dim>{exception}\n"
)
_CONSOLE_CORE_KEYS = (
    "error_id",
    "http_method",
    "http_route",
    "status_code",
    "duration_ms",
    "request_id",
)
_CONSOLE_KEY_ALIASES = {
    "error_id": "err",
    "request_id": "req",
    "http_method": "method",
    "http_route": "route",
    "status_code": "status",
    "duration_ms": "duration",
}
_CONSOLE_HIGHLIGHT_COLORS = {"http_method": "magenta", "http_route": "cyan"}

# 内部 extra key，由 console LogRecord 中其它部分展示
_CONSOLE_INTERNAL_KEYS = {"context", "event", "logging_name", "service"}
# extra 展示显示——数量，长度
_CONSOLE_EXTRA_LIMIT = 4
_CONSOLE_VALUE_LIMIT = 64


# 推荐的 logger 使用分级策略：
# 1. 普通运行日志推荐直接 logger.info/debug(...)，不用绑定 event；
# 2. 只有字段需要在后续日志检索，或者有检查价值时再通过 logger.bind(field=value) 绑定相关字段；
# 3. HTTP/SSE、安全决策、后台任务和业务生命周期等稳定事件推荐绑定对应的 event。

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
# 识别为噪音的标准 logging 对象
_NOISY_CONSOLE_LOGGERS = (
    "alembic",
    "fastapi",
    "openai._base_client",
    "uvicorn",
    "watchfiles",
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
                    "filter": (
                        _console_filter
                        if app_settings.log_format == "console"
                        else None
                    ),
                    "serialize": app_settings.log_format == "json",
                    "enqueue": True,
                    "backtrace": app_settings.log_format != "console",
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
        standard_logger.disabled = False
        standard_logger.propagate = True
        standard_logger.setLevel(logging.NOTSET)

    # 抬高标准 logging 默认输出级别以减少噪声和泄露。
    logging.getLogger("uvicorn.access").disabled = True
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
    """控制台日志输出渲染为紧凑的开发者可读日志。"""
    level_name = record["level"].name
    local_time = record["time"].astimezone().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    exception = (
        "\n{exception}"
        if record["exception"] is not None and record["level"].no >= logging.ERROR
        else ""
    )
    return _CONSOLE_FORMAT.format(
        local_time=local_time,
        level=_CONSOLE_LEVEL_NAMES.get(level_name, level_name[:4]),
        component=_escape_format_literal(_console_component(record)),
        context=_console_context(record["extra"]),
        location=_escape_format_literal(f"@{record['file'].name}:{record['line']}"),
        exception=exception,
    )


def _console_filter(record: dict[str, Any]) -> bool:
    """Console 隐藏第三方 INFO 噪声，文件 sink 仍接收原始记录。"""
    extra = record["extra"]
    logging_name = extra.get("logging_name")
    if not isinstance(logging_name, str) or record["level"].no >= logging.WARNING:
        return True
    return not any(
        logging_name == name or logging_name.startswith(f"{name}.")
        for name in _NOISY_CONSOLE_LOGGERS
    )


def _console_component(record: dict[str, Any]) -> str:
    """component 展示 event > logging_name > logger name(默认为 module name)"""
    extra = record["extra"]
    event = extra.get("event")
    if event:
        return str(event)

    component = str(extra.get("logging_name") or record["name"] or "application")
    return component.removeprefix("app.")


def _console_context(extra: dict[str, Any]) -> str:
    """核心字段优先，其余 bind 字段按原始顺序补足。"""
    rendered: list[str] = []
    candidate_keys = dict.fromkeys((*_CONSOLE_CORE_KEYS, *extra))  # 候选 keys
    for key in candidate_keys:
        if key in _CONSOLE_INTERNAL_KEYS or key not in extra or extra[key] is None:
            continue

        name = _escape_format_literal(_CONSOLE_KEY_ALIASES.get(key, key))
        value = _escape_format_literal(_console_value(key, extra[key]))
        item = f"[{name}={value}]"
        # 部分 extra 字段设置高亮
        if color := _CONSOLE_HIGHLIGHT_COLORS.get(key):
            item = f"<bold><{color}>{item}</{color}></bold>"
        rendered.append(item)

        if len(rendered) == _CONSOLE_EXTRA_LIMIT:
            break

    return f"  {' '.join(rendered)}" if rendered else ""


def _console_value(key: str, value: Any) -> str:
    # error_id, request_id 显示前 8 位，避免过长
    if key in {"error_id", "request_id"}:
        rendered_id = str(value)
        return rendered_id[:8]

    # duration_ms 转换为更友好展示
    if key == "duration_ms" and isinstance(value, int | float):
        if value >= 1000:
            return f"{value / 1000:.2f}s"
        return f"{value:g}ms"

    # 简单字符限制最大展示长度
    if isinstance(value, str) and re.compile(r"^[\w./:@+-]+$").fullmatch(value):
        rendered = value
    else:
        rendered = json.dumps(
            value, ensure_ascii=False, default=str, separators=(",", ":")
        )
    return (
        rendered
        if len(rendered) <= _CONSOLE_VALUE_LIMIT
        else f"{rendered[: _CONSOLE_VALUE_LIMIT - 1]}…"
    )


def _escape_format_literal(value: str) -> str:
    """转义 Loguru format 占位符和颜色标记。"""
    return (
        value.replace("\\", "\\\\")
        .replace("{", "{{")
        .replace("}", "}}")
        .replace("<", "\\<")
    )


def _write_console(message: Any) -> None:
    # 运行时读取 sys.stderr，兼容测试捕获以及宿主进程替换输出流。
    sys.stderr.write(str(message))


def _use_utc_time(record: dict[str, Any]) -> None:
    record["time"] = record["time"].astimezone(UTC)
