"""SQLite persistence for orders: CRUD, status transitions, and queries for KDS.

Works entirely without an API key.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from datetime import date, datetime, time, timedelta
from pathlib import Path

from app import config
from app.orders.models import DeliveryType, Order, OrderItem, OrderStatus

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    number INTEGER NOT NULL UNIQUE,
    status TEXT NOT NULL,
    items_json TEXT NOT NULL,
    delivery_type TEXT NOT NULL,
    customer_name TEXT NOT NULL DEFAULT '',
    delivery_phone TEXT NOT NULL DEFAULT '',
    delivery_address TEXT NOT NULL DEFAULT '',
    total REAL NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


def _connect() -> sqlite3.Connection:
    Path(config.DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_column(conn: sqlite3.Connection, column: str) -> None:
    """Add a column to an existing database, ignoring duplicates."""
    try:
        conn.execute(f"ALTER TABLE orders ADD COLUMN {column}")
    except sqlite3.OperationalError as exc:
        if "duplicate column name" in str(exc):
            return
        raise


def init_db() -> None:
    """Create the schema, migrate older databases, and add the day-query index."""
    conn = _connect()
    try:
        conn.execute(SCHEMA)
        _ensure_column(conn, "delivery_phone TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "delivery_address TEXT NOT NULL DEFAULT ''")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at)"
        )
        conn.commit()
        logger.info("Orders database initialized at %s", config.DB_PATH)
    except Exception:
        logger.exception("Failed to initialize database at %s", config.DB_PATH)
        raise
    finally:
        conn.close()


def _row_to_order(row: sqlite3.Row) -> Order:
    keys = row.keys()
    return Order(
        id=row["id"],
        number=row["number"],
        status=OrderStatus(row["status"]),
        items=[OrderItem(**item) for item in json.loads(row["items_json"])],
        delivery_type=DeliveryType(row["delivery_type"]),
        customer_name=row["customer_name"],
        delivery_phone=row["delivery_phone"] if "delivery_phone" in keys else "",
        delivery_address=row["delivery_address"] if "delivery_address" in keys else "",
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def create_order(
    items: list[OrderItem],
    delivery_type: DeliveryType,
    customer_name: str = "",
    delivery_phone: str = "",
    delivery_address: str = "",
) -> Order:
    """Insert a new order with status `pending` and return it."""
    conn = _connect()
    try:
        conn.execute(SCHEMA)
        number = conn.execute(
            "SELECT COALESCE(MAX(number), 0) + 1 FROM orders"
        ).fetchone()[0]
        now = datetime.now()
        total = round(sum(item.total for item in items), 2)
        cursor = conn.execute(
            "INSERT INTO orders "
            "(number, status, items_json, delivery_type, customer_name, "
            " delivery_phone, delivery_address, total, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                number,
                OrderStatus.pending.value,
                json.dumps([item.model_dump() for item in items]),
                delivery_type.value,
                customer_name,
                delivery_phone,
                delivery_address,
                total,
                now.isoformat(),
                now.isoformat(),
            ),
        )
        conn.commit()
        order = Order(
            id=cursor.lastrowid,
            number=number,
            status=OrderStatus.pending,
            items=items,
            delivery_type=delivery_type,
            customer_name=customer_name,
            delivery_phone=delivery_phone,
            delivery_address=delivery_address,
            created_at=now,
            updated_at=now,
        )
        logger.info(
            "Order created: id=%s number=%s items=%d total=%.2f delivery=%s customer=%r",
            order.id, order.number, len(items), total, delivery_type.value, customer_name,
        )
        return order
    except Exception:
        logger.exception("Failed to create order with %d item(s)", len(items))
        raise
    finally:
        conn.close()


def get_order(order_id: int) -> Order | None:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM orders WHERE id = ?", (order_id,)
        ).fetchone()
        return _row_to_order(row) if row else None
    finally:
        conn.close()


def update_status(order_id: int, new_status: OrderStatus | str) -> Order:
    """Set an order's status. Raises KeyError if the order does not exist."""
    status = (
        new_status
        if isinstance(new_status, OrderStatus)
        else OrderStatus(new_status)
    )
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT id, status FROM orders WHERE id = ?", (order_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"Order {order_id} not found")
        old_status = OrderStatus(row["status"])
        now = datetime.now()
        conn.execute(
            "UPDATE orders SET status = ?, updated_at = ? WHERE id = ?",
            (status.value, now.isoformat(), order_id),
        )
        conn.commit()
        updated = conn.execute(
            "SELECT * FROM orders WHERE id = ?", (order_id,)
        ).fetchone()
        logger.info(
            "Order %s status: %s -> %s", order_id, old_status.value, status.value
        )
        return _row_to_order(updated)
    except Exception:
        logger.exception("Failed to update status of order %s", order_id)
        raise
    finally:
        conn.close()


def list_active_orders(limit: int = 100) -> list[Order]:
    """All orders that are not completed, newest first."""
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM orders WHERE status != ? ORDER BY created_at DESC LIMIT ?",
            (OrderStatus.completed.value, limit),
        ).fetchall()
        orders = [_row_to_order(row) for row in rows]
        logger.debug("list_active_orders returned %d order(s)", len(orders))
        return orders
    except Exception:
        logger.exception("Failed to list active orders")
        raise
    finally:
        conn.close()


def _day_range(day: date) -> tuple[str, str]:
    """ISO string bounds [day start, next day start) for a local day.

    `created_at` is persisted via `datetime.now().isoformat()` (naive local
    time), so the day boundaries are computed as local midnight.
    """
    start = datetime.combine(day, time.min)
    end = datetime.combine(day + timedelta(days=1), time.min)
    return start.isoformat(), end.isoformat()


def _escape_like(value: str) -> str:
    """Escape SQLite LIKE wildcards so user input is matched literally."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def search_orders(
    day: date,
    q: str | None = None,
    status: OrderStatus | str | None = None,
    limit: int = 100,
) -> tuple[list[Order], int]:
    """Orders created on a local `day`, newest first, with optional filters.

    `q` is a case-insensitive LIKE search over the order number (as text), the
    customer name and the serialized items JSON. Returns `(orders, total)`:
    `orders` respects `limit`, `total` counts every matching row so the UI can
    show "showing the first N of M".
    """
    status_value = None
    if status is not None:
        status_value = (
            status.value if isinstance(status, OrderStatus) else OrderStatus(status).value
        )

    start, end = _day_range(day)
    where = ["created_at >= ?", "created_at < ?"]
    params: list = [start, end]
    if status_value is not None:
        where.append("status = ?")
        params.append(status_value)
    if q and q.strip():
        pattern = f"%{_escape_like(q.strip().lower())}%"
        where.append(
            "(LOWER(CAST(number AS TEXT)) LIKE ? ESCAPE '\\' "
            "OR LOWER(customer_name) LIKE ? ESCAPE '\\' "
            "OR LOWER(items_json) LIKE ? ESCAPE '\\')"
        )
        params.extend([pattern, pattern, pattern])

    where_sql = " AND ".join(where)
    conn = _connect()
    try:
        total = conn.execute(
            f"SELECT COUNT(*) FROM orders WHERE {where_sql}", params
        ).fetchone()[0]
        rows = conn.execute(
            f"SELECT * FROM orders WHERE {where_sql} ORDER BY created_at DESC LIMIT ?",
            [*params, limit],
        ).fetchall()
        orders = [_row_to_order(row) for row in rows]
        logger.debug(
            "search_orders: day=%s q=%r status=%s -> %d of %d order(s)",
            day.isoformat(), q, status_value, len(orders), total,
        )
        return orders, total
    except Exception:
        logger.exception("Failed to search orders for day %s", day.isoformat())
        raise
    finally:
        conn.close()


def delete_orders_on(day: date) -> int:
    """Hard-delete every order created on the given local day. Returns count."""
    start, end = _day_range(day)
    conn = _connect()
    try:
        cursor = conn.execute(
            "DELETE FROM orders WHERE created_at >= ? AND created_at < ?",
            (start, end),
        )
        conn.commit()
        deleted = cursor.rowcount
        logger.warning("Deleted %d order(s) for day %s", deleted, day.isoformat())
        return deleted
    except Exception:
        logger.exception("Failed to delete orders for day %s", day.isoformat())
        raise
    finally:
        conn.close()


def delete_order(order_id: int) -> bool:
    """Hard-delete a single order by id. Returns True if a row was deleted."""
    conn = _connect()
    try:
        cursor = conn.execute(
            "DELETE FROM orders WHERE id = ?", (order_id,)
        )
        conn.commit()
        deleted = cursor.rowcount > 0
        if deleted:
            logger.warning("Deleted order %s", order_id)
        else:
            logger.debug("Order %s not found; nothing deleted", order_id)
        return deleted
    except Exception:
        logger.exception("Failed to delete order %s", order_id)
        raise
    finally:
        conn.close()


def list_history(limit: int = 50) -> list[Order]:
    """Recently finished orders (status `completed`), newest first."""
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM orders WHERE status = ? "
            "ORDER BY created_at DESC LIMIT ?",
            (OrderStatus.completed.value, limit),
        ).fetchall()
        orders = [_row_to_order(row) for row in rows]
        logger.debug("list_history returned %d completed order(s)", len(orders))
        return orders
    except Exception:
        logger.exception("Failed to list order history")
        raise
    finally:
        conn.close()


def list_recent_orders(limit: int = 50) -> list[Order]:
    """Most recent orders regardless of status, newest first."""
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM orders ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [_row_to_order(row) for row in rows]
    finally:
        conn.close()


def orders_since(iso_timestamp: str) -> list[Order]:
    """Orders created after a given ISO timestamp (used for KDS polling fallback)."""
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM orders WHERE created_at >= ? ORDER BY created_at DESC",
            (iso_timestamp,),
        ).fetchall()
        return [_row_to_order(row) for row in rows]
    finally:
        conn.close()
