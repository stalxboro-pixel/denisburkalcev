from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.config import settings


def setup_logging() -> logging.Logger:
    # Centralised logging with rotation; secrets must never be logged.
    settings.log_dir.mkdir(parents=True, exist_ok=True)
    log_path: Path = settings.log_dir / settings.log_file

    level = getattr(logging, settings.log_level, logging.INFO)
    fmt = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
    formatter = logging.Formatter(fmt)

    root = logging.getLogger()
    root.setLevel(level)

    # Avoid duplicate handlers when called twice (e.g., tests).
    for handler in list(root.handlers):
        root.removeHandler(handler)

    stream = logging.StreamHandler()
    stream.setFormatter(formatter)
    stream.setLevel(level)
    root.addHandler(stream)

    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=settings.log_max_bytes,
        backupCount=settings.log_backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)
    root.addHandler(file_handler)

    # aiogram is verbose at DEBUG; tame it unless explicitly requested.
    logging.getLogger("aiogram.event").setLevel(max(level, logging.INFO))
    logging.getLogger("aiohttp.access").setLevel(logging.WARNING)

    return logging.getLogger("bot")
