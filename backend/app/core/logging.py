import json
import logging
import logging.config
import sys
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path

from app.config import BASE_DIR, settings

_CONFIGURED = False

TEXT_FORMAT = (
    "%(asctime)s %(levelname)s [%(request_id)s] %(name)s:%(lineno)d - %(message)s"
)
COLOR_TEXT_FORMAT = (
    "%(asctime)s %(color_level)s [%(request_id)s] %(name)s:%(lineno)d - %(message)s"
)

RESET_COLOR = "\033[0m"
LEVEL_COLORS = {
    "DEBUG": "\033[36m",  # cyan
    "INFO": "\033[32m",  # green
    "WARNING": "\033[33m",  # yellow
    "ERROR": "\033[31m",  # red
    "CRITICAL": "\033[1;31m",  # bold red
}

EXTRA_FIELDS = (
    "user_id",
    "method",
    "path",
    "status_code",
    "duration_ms",
    "reservation_id",
    "actor_id",
    "action",
    "from_status",
    "to_status",
    "error_code",
    "slow",
)

request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")


class RequestIdFilter(logging.Filter):
    def filter(self, record):
        if not getattr(record, "request_id", None):
            record.request_id = request_id_ctx.get() or "-"
        return True


class TextFormatter(logging.Formatter):
    def __init__(self, fmt: str = TEXT_FORMAT):
        super().__init__(
            fmt=fmt,
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    def format(self, record):
        record.request_id = getattr(record, "request_id", None) or "-"
        base = super().format(record)
        extras = []
        for key in EXTRA_FIELDS:
            value = getattr(record, key, None)
            if value is not None:
                extras.append(f"{key}={value}")
        return base + (" " + " ".join(extras) if extras else "")


class ColorTextFormatter(TextFormatter):
    def __init__(self, enabled: bool = True, stream=None):
        super().__init__(COLOR_TEXT_FORMAT)
        self.enabled = enabled
        self.stream = stream

    def format(self, record):
        stream = self.stream or sys.stdout
        use_color = self.enabled and getattr(stream, "isatty", lambda: False)()
        color = LEVEL_COLORS.get(record.levelname, "")
        record.color_level = (
            f"{color}{record.levelname}{RESET_COLOR}" if use_color else record.levelname
        )
        return super().format(record)


class JsonFormatter(logging.Formatter):
    def format(self, record):
        record.request_id = getattr(record, "request_id", None) or "-"
        payload = {
            "timestamp": datetime.fromtimestamp(record.created)
            .astimezone()
            .isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": record.request_id,
            "module": record.module,
            "line": record.lineno,
            "function": record.funcName,
        }
        for key in EXTRA_FIELDS:
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack"] = self.formatStack(record.stack_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(force: bool = False):
    global _CONFIGURED
    if _CONFIGURED and not force:
        return

    log_format = (
        settings.log_format if settings.log_format in ("text", "json") else "text"
    )
    level_name = settings.log_level.upper()
    if level_name not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        level_name = "INFO"

    handlers = {
        "console": {
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
            "formatter": (
                "color_text"
                if log_format == "text" and settings.log_color
                else log_format
            ),
            "filters": ["request_id"],
        }
    }

    if settings.log_to_file:
        try:
            log_dir = Path(settings.log_dir)
            if not log_dir.is_absolute():
                log_dir = BASE_DIR / log_dir
            log_dir.mkdir(parents=True, exist_ok=True)

            handlers["file"] = {
                "class": "logging.handlers.RotatingFileHandler",
                "filename": str(log_dir / "app.log"),
                "maxBytes": settings.log_max_bytes,
                "backupCount": settings.log_backup_count,
                "encoding": "utf-8",
                "formatter": log_format,
                "filters": ["request_id"],
            }
        except OSError:
            pass

    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {
            "request_id": {"()": "app.core.logging.RequestIdFilter"},
        },
        "formatters": {
            "text": {"()": "app.core.logging.TextFormatter"},
            "color_text": {
                "()": "app.core.logging.ColorTextFormatter",
                "enabled": settings.log_color,
            },
            "json": {"()": "app.core.logging.JsonFormatter"},
        },
        "handlers": handlers,
        "root": {
            "level": level_name,
            "handlers": list(handlers.keys()),
        },
        "loggers": {
            # 访问日志由自定义中间件输出，关闭 uvicorn 自带的
            "uvicorn.access": {"handlers": [], "level": "WARNING", "propagate": False},
            "uvicorn.error": {"handlers": [], "level": "INFO", "propagate": True},
            "uvicorn": {"handlers": [], "level": "INFO", "propagate": True},
            "httpx": {"handlers": [], "level": "WARNING", "propagate": True},
            "sqlalchemy.engine": {
                "handlers": [],
                "level": "WARNING",
                "propagate": True,
            },
        },
    }
    logging.config.dictConfig(config)
    _CONFIGURED = True
