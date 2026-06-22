"""Buyurtmalar va to'lov tranzaksiyalari uchun SQLite ombor (async wrapper)."""
from __future__ import annotations

import asyncio
import sqlite3
import time
import uuid
from typing import Any, Optional

DB_PATH = "orders.db"

# Buyurtma holatlari
CREATED = "created"
PAID = "paid"
DELIVERING = "delivering"
DELIVERED = "delivered"
CANCELLED = "cancelled"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _init() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS orders (
                order_id    TEXT PRIMARY KEY,
                user_id     INTEGER,
                chat_id     INTEGER,
                lang        TEXT,
                topic       TEXT,
                field       TEXT,
                author      TEXT,
                keywords    TEXT,
                pages       INTEGER,
                amount      INTEGER,        -- so'mda
                premium     INTEGER DEFAULT 0,  -- 1 = jadval+diagrammali (premium)
                status      TEXT,
                created_at  INTEGER,
                paid_at     INTEGER,
                delivered_at INTEGER,
                click_prepare_id TEXT
            )
            """
        )
        # Eski bazalar uchun migratsiya — 'premium' ustuni bo'lmasa qo'shamiz
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(orders)")}
        if "premium" not in cols:
            conn.execute("ALTER TABLE orders ADD COLUMN premium INTEGER DEFAULT 0")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS payme_tx (
                rowid_      INTEGER PRIMARY KEY AUTOINCREMENT,
                payme_id    TEXT UNIQUE,
                order_id    TEXT,
                amount      INTEGER,         -- tiyinda
                state       INTEGER,
                create_time INTEGER,
                perform_time INTEGER DEFAULT 0,
                cancel_time INTEGER DEFAULT 0,
                reason      INTEGER
            )
            """
        )


def init_db() -> None:
    _init()


def _create_order(data: dict[str, Any]) -> str:
    order_id = uuid.uuid4().hex[:12]
    with _connect() as conn:
        conn.execute(
            """INSERT INTO orders
               (order_id, user_id, chat_id, lang, topic, field, author,
                keywords, pages, amount, premium, status, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                order_id,
                data["user_id"],
                data["chat_id"],
                data["lang"],
                data["topic"],
                data["field"],
                data["author"],
                data["keywords"],
                data["pages"],
                data["amount"],
                1 if data.get("premium") else 0,
                CREATED,
                int(time.time()),
            ),
        )
    return order_id


def _get_order(order_id: str) -> Optional[dict]:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM orders WHERE order_id=?", (order_id,)
        ).fetchone()
    return dict(row) if row else None


def _set_status(order_id: str, status: str, *, paid: bool = False,
                delivered: bool = False) -> None:
    sets = ["status=?"]
    vals: list[Any] = [status]
    if paid:
        sets.append("paid_at=?")
        vals.append(int(time.time()))
    if delivered:
        sets.append("delivered_at=?")
        vals.append(int(time.time()))
    vals.append(order_id)
    with _connect() as conn:
        conn.execute(f"UPDATE orders SET {', '.join(sets)} WHERE order_id=?", vals)


def _try_begin_delivery(order_id: str) -> bool:
    """Faqat 'paid' holatdagi buyurtmani 'delivering' ga o'tkazadi (atomik).
    True qaytarsa — bu chaqiruv yetkazib berishni boshlashi mumkin."""
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE orders SET status=? WHERE order_id=? AND status=?",
            (DELIVERING, order_id, PAID),
        )
        return cur.rowcount > 0


def _set_click_prepare(order_id: str, prepare_id: str) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE orders SET click_prepare_id=? WHERE order_id=?",
            (prepare_id, order_id),
        )


def _orders_by_user(user_id: int, limit: int = 5) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM orders WHERE user_id=? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def _stats() -> dict:
    paid_states = (PAID, DELIVERING, DELIVERED)
    with _connect() as conn:
        total_orders = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        delivered = conn.execute(
            "SELECT COUNT(*) FROM orders WHERE status=?", (DELIVERED,)
        ).fetchone()[0]
        paid_cnt = conn.execute(
            f"SELECT COUNT(*) FROM orders WHERE status IN ({','.join('?'*len(paid_states))})",
            paid_states,
        ).fetchone()[0]
        revenue = conn.execute(
            f"SELECT COALESCE(SUM(amount),0) FROM orders "
            f"WHERE status IN ({','.join('?'*len(paid_states))})",
            paid_states,
        ).fetchone()[0]
    return {
        "total_orders": total_orders,
        "paid": paid_cnt,
        "delivered": delivered,
        "revenue": revenue,
    }


# --- Payme tranzaksiyalari ---
def _payme_get_by_id(payme_id: str) -> Optional[dict]:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM payme_tx WHERE payme_id=?", (payme_id,)
        ).fetchone()
    return dict(row) if row else None


def _payme_get_by_order(order_id: str) -> Optional[dict]:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM payme_tx WHERE order_id=? AND state IN (1,2)",
            (order_id,),
        ).fetchone()
    return dict(row) if row else None


def _payme_create(payme_id: str, order_id: str, amount: int,
                  create_time: int) -> dict:
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO payme_tx (payme_id, order_id, amount, state, create_time)
               VALUES (?,?,?,?,?)""",
            (payme_id, order_id, amount, 1, create_time),
        )
        rowid = cur.lastrowid
    return _payme_get_by_id(payme_id)


def _payme_update(payme_id: str, **fields: Any) -> None:
    cols = ", ".join(f"{k}=?" for k in fields)
    vals = list(fields.values()) + [payme_id]
    with _connect() as conn:
        conn.execute(f"UPDATE payme_tx SET {cols} WHERE payme_id=?", vals)


def _payme_statement(frm: int, to: int) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM payme_tx WHERE create_time BETWEEN ? AND ?",
            (frm, to),
        ).fetchall()
    return [dict(r) for r in rows]


# --- Async wrapperlar ---
async def create_order(data: dict[str, Any]) -> str:
    return await asyncio.to_thread(_create_order, data)


async def get_order(order_id: str) -> Optional[dict]:
    return await asyncio.to_thread(_get_order, order_id)


async def set_status(order_id: str, status: str, **kw: Any) -> None:
    await asyncio.to_thread(lambda: _set_status(order_id, status, **kw))


async def try_begin_delivery(order_id: str) -> bool:
    return await asyncio.to_thread(_try_begin_delivery, order_id)


async def set_click_prepare(order_id: str, prepare_id: str) -> None:
    await asyncio.to_thread(_set_click_prepare, order_id, prepare_id)


async def orders_by_user(user_id: int, limit: int = 5) -> list[dict]:
    return await asyncio.to_thread(_orders_by_user, user_id, limit)


async def stats() -> dict:
    return await asyncio.to_thread(_stats)


# Payme — webhook sinxron ishlagani uchun sync funksiyalar ham ochiq qoladi
payme_get_by_id = _payme_get_by_id
payme_get_by_order = _payme_get_by_order
payme_create = _payme_create
payme_update = _payme_update
payme_statement = _payme_statement
get_order_sync = _get_order
set_status_sync = _set_status
try_begin_delivery_sync = _try_begin_delivery
