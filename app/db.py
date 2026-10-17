"""Хранилище: SQLite через стандартный sqlite3.

Отдельная СУБД здесь не нужна: объём — заявки с одного сайта. Если проект
вырастет, меняется только этот файл.
"""
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

def db_path() -> str:
    """Путь читается при каждом обращении: тесты подменяют его переменной окружения."""
    return os.environ.get("LEADBOX_DB", "data/leadbox.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS leads (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at  TEXT NOT NULL,
    name        TEXT NOT NULL,
    contact_type TEXT NOT NULL,
    contact     TEXT NOT NULL,
    message     TEXT NOT NULL DEFAULT '',
    utm_source  TEXT NOT NULL DEFAULT '',
    utm_campaign TEXT NOT NULL DEFAULT '',
    variant     TEXT NOT NULL DEFAULT 'A',
    ip_hash     TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_leads_contact ON leads(contact, created_at);
CREATE INDEX IF NOT EXISTS idx_leads_ip ON leads(ip_hash, created_at);

CREATE TABLE IF NOT EXISTS views (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    variant    TEXT NOT NULL
);
"""


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@contextmanager
def connect():
    path = db_path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)


def add_lead(data: dict, ip_hash: str) -> int:
    with connect() as conn:
        cur = conn.execute(
            """INSERT INTO leads (created_at, name, contact_type, contact, message,
                                  utm_source, utm_campaign, variant, ip_hash)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                now(), data["name"], data["contact_type"], data["contact"],
                data["message"], data["utm_source"], data["utm_campaign"],
                data["variant"], ip_hash,
            ),
        )
        return int(cur.lastrowid)


def find_recent(contact: str, hours: int = 24) -> sqlite3.Row | None:
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).replace(microsecond=0).isoformat()
    with connect() as conn:
        return conn.execute(
            "SELECT id, created_at FROM leads WHERE contact = ? AND created_at >= ? LIMIT 1",
            (contact, since),
        ).fetchone()


def count_from_ip(ip_hash: str, minutes: int = 60) -> int:
    since = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).replace(microsecond=0).isoformat()
    with connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM leads WHERE ip_hash = ? AND created_at >= ?",
            (ip_hash, since),
        ).fetchone()
        return int(row["n"])


def list_leads(limit: int = 50, offset: int = 0) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """SELECT id, created_at, name, contact_type, contact, message,
                      utm_source, utm_campaign, variant
               FROM leads ORDER BY id DESC LIMIT ? OFFSET ?""",
            (limit, offset),
        ).fetchall()
        return [dict(r) for r in rows]


def delete_lead(lead_id: int) -> bool:
    with connect() as conn:
        cur = conn.execute("DELETE FROM leads WHERE id = ?", (lead_id,))
        return cur.rowcount > 0


def add_view(variant: str) -> None:
    with connect() as conn:
        conn.execute("INSERT INTO views (created_at, variant) VALUES (?,?)", (now(), variant))


def stats() -> dict:
    with connect() as conn:
        views = {r["variant"]: r["n"] for r in conn.execute(
            "SELECT variant, COUNT(*) AS n FROM views GROUP BY variant")}
        leads = {r["variant"]: r["n"] for r in conn.execute(
            "SELECT variant, COUNT(*) AS n FROM leads GROUP BY variant")}
    out = {"views": {}, "leads": {}, "conversion": {}}
    for v in ("A", "B"):
        v_count = views.get(v, 0)
        l_count = leads.get(v, 0)
        out["views"][v] = v_count
        out["leads"][v] = l_count
        out["conversion"][v] = round(l_count / v_count * 100, 2) if v_count else 0.0
    out["total_leads"] = sum(leads.values())
    return out
