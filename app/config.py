from __future__ import annotations

import math
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Load .env early so all modules see env vars on import.
load_dotenv()


def _int_list(raw: str | None) -> list[int]:
    if not raw:
        return []
    out: list[int] = []
    for part in raw.replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            out.append(int(part))
        except ValueError:
            continue
    return out


def _get_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass(frozen=True)
class Settings:
    bot_token: str
    bot_username: str
    admin_ids: tuple[int, ...]
    support_contact: str

    db_path: Path

    log_level: str
    log_dir: Path
    log_file: str
    log_max_bytes: int
    log_backup_count: int

    rate_limit_seconds: float
    rate_limit_burst: int

    stars_per_rub: float
    referral_percent: int

    proxy_url: str | None

    project_root: Path = field(default_factory=lambda: Path(__file__).resolve().parent.parent)

    def stars_for_rub(self, rub: int | float) -> int:
        # Fallback conversion when product has no explicit stars price.
        return max(1, math.ceil(float(rub) * self.stars_per_rub))

    def is_admin(self, user_id: int) -> bool:
        return user_id in self.admin_ids


def load_settings() -> Settings:
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token or token.startswith("000000"):
        # Defer hard failure to bot start; allow tooling to import config.
        token = token or ""

    project_root = Path(__file__).resolve().parent.parent

    db_path = Path(os.getenv("DB_PATH", "data/bot.db"))
    if not db_path.is_absolute():
        db_path = project_root / db_path

    log_dir = Path(os.getenv("LOG_DIR", "logs"))
    if not log_dir.is_absolute():
        log_dir = project_root / log_dir

    return Settings(
        bot_token=token,
        bot_username=os.getenv("BOT_USERNAME", "wotsellerok_bot").lstrip("@"),
        admin_ids=tuple(_int_list(os.getenv("ADMIN_IDS"))),
        support_contact=os.getenv("SUPPORT_CONTACT", "BUMZILKA").lstrip("@"),
        db_path=db_path,
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        log_dir=log_dir,
        log_file=os.getenv("LOG_FILE", "bot.log"),
        log_max_bytes=int(os.getenv("LOG_MAX_BYTES", "5242880")),
        log_backup_count=int(os.getenv("LOG_BACKUP_COUNT", "5")),
        rate_limit_seconds=float(os.getenv("RATE_LIMIT_SECONDS", "0.7")),
        rate_limit_burst=int(os.getenv("RATE_LIMIT_BURST", "4")),
        stars_per_rub=float(os.getenv("STARS_PER_RUB", "1.0")),
        referral_percent=int(os.getenv("REFERRAL_PERCENT", "5")),
        proxy_url=(os.getenv("PROXY_URL") or "").strip() or None,
        project_root=project_root,
    )


settings = load_settings()
