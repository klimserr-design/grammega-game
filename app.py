import asyncio
import hashlib
import hmac
import json
import logging
import os
import random
from urllib.parse import parse_qsl, unquote

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import KeyboardButton, LabeledPrice, Message, PreCheckoutQuery, ReplyKeyboardMarkup, WebAppInfo
from aiohttp import web
from dotenv import load_dotenv

import database as db

load_dotenv()

# Берем порт из окружения (для FPS.ms), если нет - 8080
PORT = int(os.getenv("PORT", "8080"))
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBAPP_URL = os.getenv("WEBAPP_URL")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

logging.basicConfig(level=logging.INFO)
bot = Bot(BOT_TOKEN)
dp = Dispatcher()

def validate_init_data(init_data: str) -> dict | None:
    try:
        parsed = dict(parse_qsl(init_data, keep_blank_values=True))
        received_hash = parsed.pop("hash", None)
        if not received_hash: return None
        check_str = "\n".join(f"{k}={unquote(v)}" for k, v in sorted(parsed.items()))
        secret = hmac.new(BOT_TOKEN.encode(), b"WebAppData", hashlib.sha256).digest()
        expected = hmac.new(secret, check_str.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, received_hash): return None
        return json.loads(parsed.get("user", "{}"))
    except Exception:
        return None

@dp.message(CommandStart())
async def cmd_start(message: Message):
    args = message.text.split()
    if len(args) > 1 and args[1].startswith("ref_"):
        try:
            ref_id = int(args[1][4:])
            if ref_id != message.from_user.id:
                await db.set_referrer(message.from_user.id, ref_id)
        except ValueError:
            pass

    u = await db.get_user(message.from_user.id)
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🎁 Открыть кейс", web_app=WebAppInfo(url=WEBAPP_URL))]],
        resize_keyboard=True
    )
    await message.answer(
        f"Привет! Твой баланс: {u['balance']} ⭐\n"
        f"Один прокрут кейса стоит 50 ⭐.",
        reply_markup=kb
    )

@dp.pre_checkout_query()
async def pre_checkout(q: PreCheckoutQuery):
    await q.answer(ok=True)

@dp.message(F.successful_payment)
async def on_payment(message: Message):
    await db.add_balance(message.from_user.id, message.successful_payment.total_amount)
    await message.answer(f"✅ Зачислено {message.successful_payment.total_amount} ⭐")

async def api_health(request):
    return web.Response(text="OK")

async def api_me(request):
    body = await request.json()
    user = validate_init_data(body.get("initData", ""))
    if not user: return web.json_response({"ok": False}, status=403)
    u = await db.get_user(user["id"])
    return web.json_response({"ok": True, "balance": u["balance"]})

async def api_invoice(request):
    body = await request.json()
    user = validate_init_data(body.get("initData", ""))
    if not user: return web.json_response({"ok": False}, status=403)
    link = await bot.create_invoice_link(
        title="Пополнение", description="50 Stars", payload="topup",
        provider_token="", currency="XTR", prices=[LabeledPrice(label="50 Stars", amount=50)]
    )
    return web.json_response({"ok": True, "link": link})

async def api_spin(request):
    body = await request.json()
    user = validate_init_data(body.get("initData", ""))
    if not user: return web.json_response({"ok": False}, status=403)
    
    u = await db.get_user(user["id"])
    if u["balance"] < 50: return web.json_response({"ok": False, "error": "not_enough_stars"}, status=402)
    
    await db.add_balance(user["id"], -50)
    
    r = random.random() * 100
    if r < 0.1: item = {"name": "NFT 25 GRAM", "amount": "25 GRAM", "rarity": "legendary"}
    elif r < 1.1: item = {"name": "2 GRAM", "amount": "2 GRAM", "rarity": "epic"}
    elif r < 6.1: item = {"name": "0.5 GRAM", "amount": "0.5 GRAM", "rarity": "rare"}
    elif r < 21.1: item = {"name": "0.1 GRAM", "amount": "0.1 GRAM", "rarity": "uncommon"}
    else: item = {"name": "Пусто", "amount": "—", "rarity": "common"}

    await db.save_spin(user["id"], item["name"], item["amount"], item["rarity"])
    return web.json_response({"ok": True, "item": item})

async def main():
    await db.init_db()
    
    app = web.Application()
    app.router.add_get("/api/health", api_health)
    app.router.add_post("/api/me", api_me)
    app.router.add_post("/api/invoice", api_invoice)
    app.router.add_post("/api/spin", api_spin)
    app.router.add_static("/", "webapp", show_index=True)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logging.info(f"Server started on port {PORT}")

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())