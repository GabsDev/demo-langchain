"""FastAPI app: serves the KDS dashboard, REST endpoints, and the /ws WebSocket.

Boots without an API key: dashboard, SQLite, health and WebSocket all work.
"""
from __future__ import annotations

import base64
import logging
import os
import secrets
import tempfile
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

from fastapi import FastAPI, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app import config
from app.kds import ws
from app.menu import canonical
from app.orders import store
from app.orders.models import DeliveryType, OrderItem, OrderStatus

logger = logging.getLogger(__name__)

# token -> canonical markdown of a PDF menu upload awaiting confirmation.
# In-memory by design (POC); lost on restart. Matches the bot's module-level
# _pending_menu_replace pattern.
_pending_menu_upload: dict[str, str] = {}

# token -> issue time of a WebSocket handshake token for the dashboard.
# In-memory by design (POC); lost on restart. Reusable within its TTL so the
# dashboard can reconnect without refetching a token.
_ws_tokens: dict[str, datetime] = {}
_WS_TOKEN_TTL = timedelta(minutes=15)
_KDS_REALM = "KDS"


@asynccontextmanager
async def lifespan(_: FastAPI):
    store.init_db()
    logger.info("Database initialized at %s", config.DB_PATH)
    logger.info("Static files mounted from %s", config.STATIC_DIR)
    yield


app = FastAPI(title="Restaurante Bot KDS", version="0.1.0", lifespan=lifespan)

# Callback invoked after every status change (wired by run.py to notify the
# customer on Telegram). Must be callable(order) and safe to run synchronously.
app.state.order_update_callback = None

app.mount("/static", StaticFiles(directory=str(config.STATIC_DIR)), name="static")


@app.middleware("http")
async def _log_requests(request, call_next):
    """Log every HTTP request with method, path, status and duration."""
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("HTTP %s %s failed", request.method, request.url.path)
        raise
    duration_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "HTTP %s %s -> %s (%.1f ms)",
        request.method, request.url.path, response.status_code, duration_ms,
    )
    return response


def _kds_authorized(request) -> bool:
    """Validate HTTP Basic credentials for the KDS dashboard.

    Returns True immediately when auth is disabled (no KDS_PASS configured) so
    local development is untouched. Uses constant-time comparison and never
    exposes the attempted password.
    """
    if not config.has_kds_auth():
        return True
    header = request.headers.get("Authorization", "")
    if not header.startswith("Basic "):
        return False
    try:
        decoded = base64.b64decode(header[6:]).decode("utf-8")
        username, _, password = decoded.partition(":")
    except Exception:
        return False
    return secrets.compare_digest(username, config.KDS_USER) and secrets.compare_digest(
        password, config.KDS_PASS
    )


@app.middleware("http")
async def _basic_auth(request, call_next):
    """Enforce HTTP Basic Auth on every route except `/health`.

    Monitoring (uptime checks) stays open via `/health`; everything else
    requires valid credentials once KDS_PASS is configured. Failed attempts are
    logged without the password.
    """
    if request.url.path != "/health" and not _kds_authorized(request):
        client = request.client.host if request.client else "unknown"
        logger.warning("Basic auth rejected for %s from %s", request.url.path, client)
        return JSONResponse(
            status_code=401,
            content={"detail": "Authentication required"},
            headers={"WWW-Authenticate": f'Basic realm="{_KDS_REALM}"'},
        )
    return await call_next(request)


@app.get("/")
def dashboard() -> FileResponse:
    """Serve the KDS dashboard."""
    return FileResponse(config.STATIC_DIR / "index.html")


@app.get("/health")
def health() -> dict:
    index_docs: int | None = None
    try:
        from app.rag import indexer

        index_docs = indexer.count()
    except Exception:
        index_docs = None
    return {
        "status": "ok",
        "time": datetime.now().isoformat(),
        "kds_connections": ws.manager.connection_count,
        "index_docs": index_docs,
    }


@app.get("/orders")
def list_orders() -> list[dict]:
    """Active orders (initial load for the dashboard)."""
    return [order.to_dict() for order in store.list_active_orders()]


@app.get("/orders/history")
def order_history(
    date: str | None = None,
    q: str | None = None,
    status: str | None = None,
    limit: int = 100,
) -> dict:
    """Orders of a local day (default: today) with optional filters, newest first.

    `q` searches the order number, customer name and item names (case
    insensitive); `status` filters by pending/preparing/completed. Returns
    `{orders, total, date, limit}` so the UI can show "first N of M".
    """
    try:
        day = (
            datetime.strptime(date, "%Y-%m-%d").date()
            if date
            else datetime.now().date()
        )
    except ValueError:
        raise HTTPException(
            status_code=400, detail="Formato de fecha inválido, use YYYY-MM-DD"
        )
    status_enum = None
    if status:
        try:
            status_enum = OrderStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Estado inválido: {status}")
    limit = max(1, min(int(limit), 500))
    orders, total = store.search_orders(day, q=q, status=status_enum, limit=limit)
    result: list[dict] = []
    for order in orders:
        data = order.to_dict()
        data["duration_seconds"] = max(
            0, int((order.updated_at - order.created_at).total_seconds())
        )
        result.append(data)
    logger.debug(
        "Order history requested: date=%s q=%r status=%s -> %d of %d order(s)",
        day.isoformat(), q, status_enum.value if status_enum else None,
        len(result), total,
    )
    return {
        "orders": result,
        "total": total,
        "date": day.isoformat(),
        "limit": limit,
    }


class StatusUpdate(BaseModel):
    status: str


class OrderItemIn(BaseModel):
    name: str
    quantity: int = 1
    unit_price: float


class OrderCreate(BaseModel):
    items: list[OrderItemIn]
    delivery_type: str = "pickup"
    customer_name: str = ""
    delivery_phone: str = ""
    delivery_address: str = ""


class ClearDayRequest(BaseModel):
    date: str | None = None


class MenuItemCreate(BaseModel):
    section: str
    name: str
    price: float = 0.0
    description: str = ""


class MenuItemUpdate(BaseModel):
    section: str | None = None
    name: str | None = None
    price: float | None = None
    description: str | None = None


class SectionCreate(BaseModel):
    name: str


class PendingMenuToken(BaseModel):
    token: str


def _menu_changed_warning() -> None:
    logger.warning("Menu changed; run scripts/rebuild_index.py to refresh RAG")


def _item_dict(item: canonical.MenuItem) -> dict:
    return {
        "id": item.id,
        "name": item.name,
        "price": item.price,
        "description": item.description,
        "section": item.section,
    }


@app.get("/menu")
def get_menu() -> dict:
    """Canonical menu as sections/items with stable item ids."""
    menu = canonical.load_menu(config.MENU_PATH)
    return {
        "restaurant_name": menu.restaurant_name,
        "sections": [
            {
                "name": section.name,
                "items": [
                    {
                        "id": item.id,
                        "name": item.name,
                        "price": item.price,
                        "description": item.description,
                    }
                    for item in section.items
                ],
            }
            for section in menu.sections
        ],
    }


@app.post("/menu/items")
def add_menu_item(payload: MenuItemCreate) -> dict:
    """Add an item to a section and persist the canonical menu."""
    menu = canonical.load_menu(config.MENU_PATH)
    item = menu.add_item(
        payload.section,
        canonical.MenuItem(
            name=payload.name,
            price=payload.price,
            description=payload.description,
        ),
    )
    canonical.assign_item_ids(menu)
    canonical.save_menu(menu, config.MENU_PATH)
    _menu_changed_warning()
    logger.info(
        "Menu item added via API: %r in section %r", payload.name, payload.section
    )
    return _item_dict(item)


@app.put("/menu/items/{item_id}")
def update_menu_item(item_id: str, payload: MenuItemUpdate) -> dict:
    """Update an item (optionally moving it to another section)."""
    menu = canonical.load_menu(config.MENU_PATH)
    item = menu.find_item_by_id(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item no encontrado")
    if payload.section is not None:
        menu.move_item(item_id, payload.section)
    if payload.name is not None:
        item.name = payload.name
    if payload.price is not None:
        item.price = payload.price
    if payload.description is not None:
        item.description = payload.description
    canonical.assign_item_ids(menu)
    canonical.save_menu(menu, config.MENU_PATH)
    _menu_changed_warning()
    logger.info("Menu item updated via API: %r (%s)", item.name, item_id)
    return _item_dict(item)


@app.delete("/menu/items/{item_id}")
def delete_menu_item(item_id: str) -> dict:
    """Remove an item by id and persist."""
    menu = canonical.load_menu(config.MENU_PATH)
    if not menu.remove_item_by_id(item_id):
        raise HTTPException(status_code=404, detail="Item no encontrado")
    canonical.assign_item_ids(menu)
    canonical.save_menu(menu, config.MENU_PATH)
    _menu_changed_warning()
    logger.info("Menu item removed via API: %s", item_id)
    return {"ok": True}


@app.post("/menu/sections")
def add_menu_section(payload: SectionCreate) -> dict:
    """Add a new (possibly empty) section and persist."""
    menu = canonical.load_menu(config.MENU_PATH)
    section = menu.ensure_section(payload.name)
    canonical.save_menu(menu, config.MENU_PATH)
    _menu_changed_warning()
    logger.info("Menu section added via API: %r", payload.name)
    return {"ok": True, "name": section.name}


@app.delete("/menu/sections/{name}")
def delete_menu_section(name: str) -> dict:
    """Remove a section and its items. Warns if it was the last one."""
    menu = canonical.load_menu(config.MENU_PATH)
    if not menu.remove_section(name):
        raise HTTPException(status_code=404, detail="Sección no encontrada")
    if not menu.sections:
        logger.warning("Menu now has no sections after removing %r", name)
    canonical.save_menu(menu, config.MENU_PATH)
    _menu_changed_warning()
    logger.info("Menu section removed via API: %r", name)
    return {"ok": True}


@app.post("/menu/rebuild-index")
def rebuild_menu_index() -> JSONResponse:
    """Rebuild the RAG (ChromaDB) index from the canonical menu.

    Requires OPENAI_API_KEY; network calls to OpenAI embeddings make this slow.
    """
    from app.rag import indexer

    if not config.has_openai_key():
        logger.warning("RAG rebuild rejected: OPENAI_API_KEY is not configured")
        return JSONResponse(
            status_code=400,
            content={"ok": False, "error": "OPENAI_API_KEY no configurada en .env"},
        )
    try:
        docs = indexer.build_index()
    except Exception as exc:
        logger.exception("RAG index rebuild failed")
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": str(exc)},
        )
    logger.info("RAG index rebuilt via API: %d document(s)", docs)
    return JSONResponse(content={"ok": True, "docs": docs})


@app.post("/menu/upload-pdf")
async def upload_menu_pdf(file: UploadFile = File(...)) -> dict:
    """Extract a PDF menu upload and stage it for a confirm-replace.

    Returns a summary (sections/items/examples) plus a token; the caller must
    confirm via POST /menu/apply-upload before anything is persisted.
    """
    from app.menu import pdf_loader

    tmp_path: str | None = None
    try:
        fd, tmp_path = tempfile.mkstemp(suffix=".pdf", prefix="menu_upload_")
        os.close(fd)
        with open(tmp_path, "wb") as handle:
            handle.write(await file.read())
        logger.info("Menu PDF upload started via API (file=%r)", file.filename)

        markdown, used_llm = pdf_loader.pdf_to_canonical(tmp_path)
        parsed = canonical.parse_menu(markdown)
        sections = len([section for section in parsed.sections if section.items])
        items = len(parsed.items)
        logger.info(
            "Menu PDF parsed via API: %d section(s), %d item(s), used_llm=%s",
            sections, items, used_llm,
        )
        if items == 0:
            return JSONResponse(
                status_code=400,
                content={
                    "ok": False,
                    "error": (
                        "No pude identificar ítems en el PDF. Configurá "
                        "OPENAI_API_KEY para estructurar el menú automáticamente "
                        "o revisalo con python scripts/ingest_pdf.py <archivo>."
                    ),
                },
            )

        token = uuid.uuid4().hex[:12]
        _pending_menu_upload[token] = markdown
        response: dict = {
            "ok": True,
            "token": token,
            "sections": sections,
            "items": items,
            "examples": [
                f"{item.name} — {canonical.format_price(item.price)}"
                for item in parsed.items[:3]
            ],
            "used_llm": used_llm,
        }
        if not used_llm:
            response["warning"] = (
                "Sin OPENAI_API_KEY el texto se extrajo sin limpiar; "
                "el menú puede necesitar revisión manual."
            )
        logger.info("Menu PDF upload staged via API: token=%s", token)
        return response
    except Exception:
        logger.exception("Menu PDF upload processing failed")
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "error": (
                    "No pude procesar el PDF: no se pudo extraer texto. "
                    "Revisalo o configurá OPENAI_API_KEY."
                ),
            },
        )
    finally:
        if tmp_path is not None:
            try:
                os.remove(tmp_path)
            except OSError:
                logger.debug("Could not remove temp file %s", tmp_path)


@app.post("/menu/apply-upload")
def apply_menu_upload(payload: PendingMenuToken) -> dict:
    """Confirm a staged PDF upload: replace the menu (destructive) and rebuild RAG."""
    markdown = _pending_menu_upload.pop(payload.token, None)
    if markdown is None:
        return JSONResponse(
            status_code=400,
            content={"ok": False, "error": "No hay ningún menú pendiente por reemplazar."},
        )

    menu = canonical.parse_menu(markdown)
    canonical.assign_item_ids(menu)
    canonical.save_menu(menu, config.MENU_PATH)
    logger.warning(
        "Menu REPLACED via dashboard upload: %d section(s), %d item(s)",
        len(menu.sections), len(menu.items),
    )

    rag_rebuilt = False
    rag_error: str | None = None
    try:
        from app.rag import indexer

        docs = indexer.build_index(refresh=True)
        rag_rebuilt = True
        logger.info(
            "RAG index rebuilt after dashboard menu replacement: %d document(s)", docs
        )
    except Exception as exc:
        rag_error = str(exc)
        logger.exception("RAG index rebuild failed after dashboard menu replacement")

    return {
        "ok": True,
        "saved": True,
        "items": len(menu.items),
        "sections": len(menu.sections),
        "rag_rebuilt": rag_rebuilt,
        "rag_error": rag_error,
        "message": (
            "¡Menú actualizado! Corré python scripts/rebuild_index.py para "
            "actualizar el índice RAG."
            if not rag_rebuilt
            else "¡Menú actualizado! Índice RAG reconstruido."
        ),
    }


@app.post("/menu/cancel-upload")
def cancel_menu_upload(payload: PendingMenuToken) -> dict:
    """Discard a staged PDF upload without touching the current menu."""
    _pending_menu_upload.pop(payload.token, None)
    logger.info("Menu upload cancelled via API: token=%s", payload.token)
    return {"ok": True}


@app.post("/orders")
async def create_order(payload: OrderCreate) -> dict:
    """Create an order (same path the Telegram bot uses) and broadcast it."""
    items = [
        OrderItem(item.name, item.quantity, item.unit_price) for item in payload.items
    ]
    try:
        order = store.create_order(
            items,
            DeliveryType(payload.delivery_type),
            customer_name=payload.customer_name,
            delivery_phone=payload.delivery_phone,
            delivery_address=payload.delivery_address,
        )
    except Exception:
        logger.exception("Failed to create order with %d item(s)", len(items))
        raise
    logger.info(
        "Order created via API: id=%s number=%s items=%d", order.id, order.number, len(items)
    )
    await ws.manager.broadcast_order(order, "order.created")
    return order.to_dict()


@app.post("/orders/clear-day")
def clear_day(payload: ClearDayRequest) -> dict:
    """Hard-delete every order created on a given local day (default: today).

    Destructive on purpose: the day's orders are erased from SQLite and cannot
    be recovered. Only deletes the date explicitly sent by the client.
    """
    if payload.date:
        try:
            day = datetime.strptime(payload.date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(
                status_code=400, detail="Formato de fecha inválido, use YYYY-MM-DD"
            )
    else:
        day = datetime.now().date()
    deleted = store.delete_orders_on(day)
    logger.warning(
        "Orders cleared via API for day %s: %d deleted", day.isoformat(), deleted
    )
    return {"ok": True, "deleted": deleted, "date": day.isoformat()}


@app.delete("/orders/{order_id}")
async def delete_order(order_id: int) -> dict:
    """Hard-delete a single order and broadcast `order.deleted` to dashboards."""
    deleted = store.delete_order(order_id)
    if not deleted:
        logger.info("Order %s not found for delete via API", order_id)
        return JSONResponse(
            status_code=404,
            content={"ok": False, "error": "Pedido no encontrado"},
        )
    logger.warning("Order %s deleted via API", order_id)
    await ws.manager.broadcast({"type": "order.deleted", "order_id": order_id})
    return {"ok": True, "deleted": True}


def _notify(order) -> None:
    callback = app.state.order_update_callback
    if callback is None:
        return
    try:
        callback(order)
    except Exception:
        logger.exception("order update callback failed")


@app.post("/orders/{order_id}/status")
async def change_status(order_id: int, payload: StatusUpdate) -> dict:
    """REST fallback to advance an order's status."""
    try:
        order = store.update_status(order_id, payload.status)
    except Exception:
        logger.exception("Failed to change status of order %s", order_id)
        raise
    logger.info(
        "Order %s status changed via API -> %s", order.id, order.status.value
    )
    await ws.manager.broadcast_order(order, "order.updated")
    _notify(order)
    return order.to_dict()


def _prune_ws_tokens() -> None:
    """Drop expired WebSocket tokens (lazy; runs on each /ws-token issue)."""
    now = datetime.now()
    expired = [
        token for token, issued in _ws_tokens.items() if now - issued > _WS_TOKEN_TTL
    ]
    for token in expired:
        _ws_tokens.pop(token, None)
        logger.debug("Pruned expired WebSocket token %s", token)


@app.get("/ws-token")
def ws_token() -> dict:
    """Issue a short-lived WebSocket handshake token for the dashboard."""
    _prune_ws_tokens()
    token = secrets.token_urlsafe(24)
    _ws_tokens[token] = datetime.now()
    logger.info(
        "WebSocket token issued (valid %d min)",
        int(_WS_TOKEN_TTL.total_seconds() / 60),
    )
    return {"token": token, "expires_in": int(_WS_TOKEN_TTL.total_seconds())}


@app.websocket("/ws")
async def websocket_endpoint(socket: WebSocket) -> None:
    """Real-time channel: pushes init/order.created/order.updated events and
    accepts `status.change` messages from the dashboard."""
    if config.has_kds_auth():
        token = socket.query_params.get("token")
        issued = _ws_tokens.get(token) if token else None
        if issued is None or datetime.now() - issued > _WS_TOKEN_TTL:
            client = socket.client.host if socket.client else "unknown"
            logger.warning(
                "WebSocket rejected from %s: missing, invalid or expired token", client
            )
            await socket.close(code=4401)
            return
    await ws.manager.connect(socket)
    client = socket.client.host if socket.client else "unknown"
    logger.info("WebSocket connected from %s", client)
    try:
        await socket.send_json(
            {
                "type": "init",
                "orders": [order.to_dict() for order in store.list_active_orders()],
            }
        )
        while True:
            message = await socket.receive_json()
            if message.get("type") == "status.change":
                logger.info(
                    "WebSocket status.change for order %s -> %s",
                    message.get("order_id"), message.get("status"),
                )
                order = store.update_status(
                    message["order_id"], message["status"]
                )
                await ws.manager.broadcast_order(order, "order.updated")
                _notify(order)
    except WebSocketDisconnect:
        ws.manager.disconnect(socket)
        logger.info("WebSocket disconnected from %s", client)
    except Exception:
        logger.exception("WebSocket error from %s", client)
        ws.manager.disconnect(socket)
