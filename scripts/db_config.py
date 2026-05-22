from __future__ import annotations

import os
from pathlib import Path


def load_local_env() -> None:
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def get_database_url() -> str:
    load_local_env()
    for key in ("SUPABASE_DB_URL", "DATABASE_URL", "AMNESIA_DB_URL"):
        value = os.getenv(key)
        if value:
            return value
    raise RuntimeError(
        "缺少数据库连接串，请在 .env 或环境变量中提供 SUPABASE_DB_URL / DATABASE_URL / AMNESIA_DB_URL"
    )
