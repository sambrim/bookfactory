"""Shared config and DB access for the Book Factory worker.

Reads the same .env the PHP side reads, so there is one source of truth.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import mysql.connector
from mysql.connector.abstracts import MySQLConnectionAbstract

ROOT = Path(__file__).resolve().parent.parent


def load_env(path: Path | None = None) -> dict[str, str]:
    path = path or (ROOT / ".env")
    if not path.is_file():
        raise SystemExit(f"Missing {path}. Copy .env.example to .env first.")

    env: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) > 1 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        env[key.strip()] = value
    return env


ENV = load_env()


def cfg(key: str, default: Any = None) -> Any:
    return os.environ.get(key) or ENV.get(key, default)


def cfg_bool(key: str, default: bool = False) -> bool:
    raw = cfg(key)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def cfg_int(key: str, default: int) -> int:
    try:
        return int(str(cfg(key, default)))
    except (TypeError, ValueError):
        return default


def connect() -> MySQLConnectionAbstract:
    return mysql.connector.connect(
        host=cfg("DB_HOST", "127.0.0.1"),
        port=cfg_int("DB_PORT", 3306),
        database=cfg("DB_NAME", "book_factory"),
        user=cfg("DB_USER"),
        password=cfg("DB_PASS"),
        charset="utf8mb4",
        collation="utf8mb4_unicode_ci",
        autocommit=True,
    )


def storage_dir() -> Path:
    configured = str(cfg("STORAGE_PATH", "storage/books"))
    path = Path(configured) if configured.startswith("/") else ROOT / configured
    path.mkdir(parents=True, exist_ok=True)
    return path
