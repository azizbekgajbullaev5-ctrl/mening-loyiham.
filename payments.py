"""Payme (Paycom) va Click Merchant API integratsiyasi: havolalar + webhook'lar."""
from __future__ import annotations

import asyncio
import base64
import hashlib
import logging
import time

from aiohttp import web

import config
import store
from fulfillment import deliver_order

logger = logging.getLogger(__name__)


# ====================== TO'LOV HAVOLALARI ======================
def payme_link(order_id: str, amount_sum: int) -> str:
    """Payme checkout havolasi (amount tiyinda)."""
    payload = (
        f"m={config.PAYME_MERCHANT_ID};"
        f"ac.{config.PAYME_ACCOUNT_FIELD}={order_id};"
        f"a={amount_sum * 100}"
    )
    encoded = base64.b64encode(payload.encode()).decode()
    return f"{config.PAYME_CHECKOUT_URL}/{encoded}"


def click_link(order_id: str, amount_sum: int) -> str:
    """Click to'lov havolasi (amount so'mda)."""
    return (
        f"{config.CLICK_BASE_URL}?service_id={config.CLICK_SERVICE_ID}"
        f"&merchant_id={config.CLICK_MERCHANT_ID}"
        f"&amount={amount_sum}&transaction_param={order_id}"
    )


# ====================== PAYME (JSON-RPC) ======================
# Payme xato kodlari
_PAYME_ERR = {
    "auth": -32504,
    "method": -32601,
    "parse": -32700,
    "account": -31050,        # buyurtma topilmadi
    "amount": -31001,         # noto'g'ri summa
    "tx_not_found": -31003,   # tranzaksiya topilmadi
    "cannot_perform": -31008, # amalni bajarib bo'lmaydi
    "already_processing": -31099,
}


def _now_ms() -> int:
    return int(time.time() * 1000)


def _payme_error(req_id, code: int, message: str, data=None) -> web.Response:
    err = {"code": code, "message": {"ru": message, "uz": message, "en": message}}
    if data is not None:
        err["data"] = data
    return web.json_response({"error": err, "id": req_id})


def _payme_ok(req_id, result: dict) -> web.Response:
    return web.json_response({"result": result, "id": req_id})


def _check_payme_auth(request: web.Request) -> bool:
    header = request.headers.get("Authorization", "")
    if not header.startswith("Basic "):
        return False
    try:
        decoded = base64.b64decode(header[6:]).decode()
    except Exception:  # noqa: BLE001
        return False
    # Format: "Paycom:<KEY>"
    _, _, key = decoded.partition(":")
    return key == config.PAYME_KEY


async def payme_handler(request: web.Request) -> web.Response:
    bot = request.app["bot"]
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        return _payme_error(None, _PAYME_ERR["parse"], "Parse error")

    req_id = body.get("id")
    if not _check_payme_auth(request):
        return _payme_error(req_id, _PAYME_ERR["auth"], "Insufficient privileges")

    method = body.get("method")
    params = body.get("params", {})

    if method == "CheckPerformTransaction":
        return await _payme_check_perform(req_id, params)
    if method == "CreateTransaction":
        return await _payme_create_tx(req_id, params)
    if method == "PerformTransaction":
        return await _payme_perform(req_id, params, bot)
    if method == "CancelTransaction":
        return await _payme_cancel(req_id, params)
    if method == "CheckTransaction":
        return await _payme_check_tx(req_id, params)
    if method == "GetStatement":
        return await _payme_statement(req_id, params)
    return _payme_error(req_id, _PAYME_ERR["method"], "Method not found")


async def _resolve_order(params: dict):
    account = params.get("account", {}) or {}
    order_id = account.get(config.PAYME_ACCOUNT_FIELD)
    if not order_id:
        return None
    return await store.get_order(order_id)


async def _payme_check_perform(req_id, params) -> web.Response:
    order = await _resolve_order(params)
    if not order:
        return _payme_error(req_id, _PAYME_ERR["account"], "Buyurtma topilmadi",
                            config.PAYME_ACCOUNT_FIELD)
    if int(params.get("amount", 0)) != order["amount"] * 100:
        return _payme_error(req_id, _PAYME_ERR["amount"], "Noto'g'ri summa")
    if order["status"] not in (store.CREATED,):
        return _payme_error(req_id, _PAYME_ERR["cannot_perform"],
                            "Buyurtma allaqachon to'langan yoki yopilgan")
    return _payme_ok(req_id, {"allow": True})


async def _payme_create_tx(req_id, params) -> web.Response:
    payme_id = params.get("id")
    existing = await asyncio.to_thread(store.payme_get_by_id, payme_id)
    if existing:
        if existing["state"] == 1:
            return _payme_ok(req_id, {
                "create_time": existing["create_time"],
                "transaction": str(existing["rowid_"]),
                "state": 1,
            })
        return _payme_error(req_id, _PAYME_ERR["cannot_perform"],
                            "Tranzaksiya holati noto'g'ri")

    order = await _resolve_order(params)
    if not order:
        return _payme_error(req_id, _PAYME_ERR["account"], "Buyurtma topilmadi",
                            config.PAYME_ACCOUNT_FIELD)
    if int(params.get("amount", 0)) != order["amount"] * 100:
        return _payme_error(req_id, _PAYME_ERR["amount"], "Noto'g'ri summa")
    if order["status"] not in (store.CREATED,):
        return _payme_error(req_id, _PAYME_ERR["cannot_perform"],
                            "Buyurtma allaqachon to'langan yoki yopilgan")

    # Boshqa faol tranzaksiya bo'lsa
    active = await asyncio.to_thread(store.payme_get_by_order, order["order_id"])
    if active:
        return _payme_error(req_id, _PAYME_ERR["already_processing"],
                            "Buyurtmada tugallanmagan tranzaksiya bor")

    tx = await asyncio.to_thread(
        store.payme_create, payme_id, order["order_id"],
        int(params["amount"]), params.get("time", _now_ms()),
    )
    return _payme_ok(req_id, {
        "create_time": tx["create_time"],
        "transaction": str(tx["rowid_"]),
        "state": 1,
    })


async def _payme_perform(req_id, params, bot) -> web.Response:
    payme_id = params.get("id")
    tx = await asyncio.to_thread(store.payme_get_by_id, payme_id)
    if not tx:
        return _payme_error(req_id, _PAYME_ERR["tx_not_found"], "Tranzaksiya topilmadi")

    if tx["state"] == 1:
        perform_time = _now_ms()
        await asyncio.to_thread(store.payme_update, payme_id, state=2,
                                perform_time=perform_time)
        await store.set_status(tx["order_id"], store.PAID, paid=True)
        asyncio.create_task(deliver_order(bot, tx["order_id"]))
        return _payme_ok(req_id, {
            "transaction": str(tx["rowid_"]),
            "perform_time": perform_time,
            "state": 2,
        })
    if tx["state"] == 2:
        return _payme_ok(req_id, {
            "transaction": str(tx["rowid_"]),
            "perform_time": tx["perform_time"],
            "state": 2,
        })
    return _payme_error(req_id, _PAYME_ERR["cannot_perform"], "Tranzaksiya bekor qilingan")


async def _payme_cancel(req_id, params) -> web.Response:
    payme_id = params.get("id")
    tx = await asyncio.to_thread(store.payme_get_by_id, payme_id)
    if not tx:
        return _payme_error(req_id, _PAYME_ERR["tx_not_found"], "Tranzaksiya topilmadi")

    reason = params.get("reason")
    if tx["state"] in (1, 2):
        new_state = -1 if tx["state"] == 1 else -2
        cancel_time = _now_ms()
        await asyncio.to_thread(store.payme_update, payme_id, state=new_state,
                                cancel_time=cancel_time, reason=reason)
        await store.set_status(tx["order_id"], store.CANCELLED)
        tx = await asyncio.to_thread(store.payme_get_by_id, payme_id)

    return _payme_ok(req_id, {
        "transaction": str(tx["rowid_"]),
        "cancel_time": tx["cancel_time"],
        "state": tx["state"],
    })


async def _payme_check_tx(req_id, params) -> web.Response:
    tx = await asyncio.to_thread(store.payme_get_by_id, params.get("id"))
    if not tx:
        return _payme_error(req_id, _PAYME_ERR["tx_not_found"], "Tranzaksiya topilmadi")
    return _payme_ok(req_id, {
        "create_time": tx["create_time"],
        "perform_time": tx["perform_time"],
        "cancel_time": tx["cancel_time"],
        "transaction": str(tx["rowid_"]),
        "state": tx["state"],
        "reason": tx["reason"],
    })


async def _payme_statement(req_id, params) -> web.Response:
    rows = await asyncio.to_thread(
        store.payme_statement, params.get("from", 0), params.get("to", _now_ms())
    )
    transactions = [{
        "id": r["payme_id"],
        "time": r["create_time"],
        "amount": r["amount"],
        "account": {config.PAYME_ACCOUNT_FIELD: r["order_id"]},
        "create_time": r["create_time"],
        "perform_time": r["perform_time"],
        "cancel_time": r["cancel_time"],
        "transaction": str(r["rowid_"]),
        "state": r["state"],
        "reason": r["reason"],
    } for r in rows]
    return _payme_ok(req_id, {"transactions": transactions})


# ====================== CLICK (Prepare/Complete) ======================
def _click_sign(parts: list) -> str:
    return hashlib.md5("".join(str(p) for p in parts).encode()).hexdigest()


def _click_resp(data: dict, error: int, note: str, extra: dict | None = None) -> web.Response:
    body = {"error": error, "error_note": note}
    body.update(extra or {})
    return web.json_response(body)


async def click_prepare(request: web.Request) -> web.Response:
    data = await request.post()
    click_trans_id = data.get("click_trans_id")
    service_id = data.get("service_id")
    merchant_trans_id = data.get("merchant_trans_id")  # bizning order_id
    amount = data.get("amount")
    action = data.get("action")
    sign_time = data.get("sign_time")
    sign_string = data.get("sign_string")

    expected = _click_sign([
        click_trans_id, service_id, config.CLICK_SECRET_KEY,
        merchant_trans_id, amount, action, sign_time,
    ])
    base = {"click_trans_id": click_trans_id, "merchant_trans_id": merchant_trans_id}
    if expected != sign_string:
        return _click_resp(data, -1, "Sign check failed", base)

    order = await store.get_order(merchant_trans_id or "")
    if not order:
        return _click_resp(data, -5, "Order not found", base)
    if abs(float(amount or 0) - order["amount"]) > 0.01:
        return _click_resp(data, -2, "Incorrect amount", base)
    if order["status"] != store.CREATED:
        return _click_resp(data, -4, "Already paid", base)

    prepare_id = str(int(time.time() * 1000))
    await store.set_click_prepare(merchant_trans_id, prepare_id)
    base["merchant_prepare_id"] = prepare_id
    return _click_resp(data, 0, "Success", base)


async def click_complete(request: web.Request) -> web.Response:
    bot = request.app["bot"]
    data = await request.post()
    click_trans_id = data.get("click_trans_id")
    service_id = data.get("service_id")
    merchant_trans_id = data.get("merchant_trans_id")
    merchant_prepare_id = data.get("merchant_prepare_id")
    amount = data.get("amount")
    action = data.get("action")
    sign_time = data.get("sign_time")
    sign_string = data.get("sign_string")
    error = int(data.get("error", "0") or "0")

    expected = _click_sign([
        click_trans_id, service_id, config.CLICK_SECRET_KEY, merchant_trans_id,
        merchant_prepare_id, amount, action, sign_time,
    ])
    base = {
        "click_trans_id": click_trans_id,
        "merchant_trans_id": merchant_trans_id,
        "merchant_confirm_id": merchant_prepare_id,
    }
    if expected != sign_string:
        return _click_resp(data, -1, "Sign check failed", base)

    order = await store.get_order(merchant_trans_id or "")
    if not order:
        return _click_resp(data, -5, "Order not found", base)
    if order.get("click_prepare_id") != merchant_prepare_id:
        return _click_resp(data, -6, "Transaction not found", base)

    if error < 0:
        await store.set_status(merchant_trans_id, store.CANCELLED)
        return _click_resp(data, -9, "Transaction cancelled", base)

    if order["status"] == store.CREATED:
        await store.set_status(merchant_trans_id, store.PAID, paid=True)
        asyncio.create_task(deliver_order(bot, merchant_trans_id))
    return _click_resp(data, 0, "Success", base)


# ====================== VEB-APP ======================
def create_web_app(bot) -> web.Application:
    app = web.Application()
    app["bot"] = bot
    if config.method_payme_enabled():
        app.router.add_post("/payme", payme_handler)
    if config.method_click_enabled():
        app.router.add_post("/click/prepare", click_prepare)
        app.router.add_post("/click/complete", click_complete)
    app.router.add_get("/health", lambda r: web.Response(text="ok"))
    return app
