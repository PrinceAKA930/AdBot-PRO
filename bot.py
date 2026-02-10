import os
import asyncio
import random
import sqlite3
from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from telethon import TelegramClient
from telethon.errors import (
    AuthRestartError,
    SendCodeUnavailableError,
    PhoneCodeInvalidError
)

# =========================
# ENV
# =========================
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS").split(",")))
LOG_CHANNEL = os.getenv("LOG_CHANNEL")

os.makedirs("sessions", exist_ok=True)

# =========================
# DATABASE
# =========================
db = sqlite3.connect("data.db")
cur = db.cursor()

cur.execute("CREATE TABLE IF NOT EXISTS chats(uid INT, chat TEXT)")
cur.execute("CREATE TABLE IF NOT EXISTS settings(uid INT, msg TEXT, interval INT)")
db.commit()

# =========================
# MEMORY
# =========================
states = {}
clients = {}
tasks = {}

# =========================
# BUTTONS
# =========================
def panel():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔐 Login", callback_data="login"),
         InlineKeyboardButton("👤 Accounts", callback_data="accounts")],

        [InlineKeyboardButton("➕ Add Chat", callback_data="add"),
         InlineKeyboardButton("➖ Remove Chat", callback_data="remove")],

        [InlineKeyboardButton("✏ Message", callback_data="msg"),
         InlineKeyboardButton("⏱ Interval", callback_data="interval")],

        [InlineKeyboardButton("▶ Start Ads", callback_data="start"),
         InlineKeyboardButton("⛔ Stop Ads", callback_data="stop")]
    ])


# =========================
# HELPERS
# =========================
def get_setting(uid):
    row = cur.execute("SELECT msg, interval FROM settings WHERE uid=?", (uid,)).fetchone()
    if not row:
        return None, 60
    return row[0], row[1]


def set_setting(uid, msg=None, interval=None):
    m, i = get_setting(uid)
    msg = msg or m
    interval = interval or i

    cur.execute("DELETE FROM settings WHERE uid=?", (uid,))
    cur.execute("INSERT INTO settings VALUES(?,?,?)", (uid, msg, interval))
    db.commit()


def get_chats(uid):
    rows = cur.execute("SELECT chat FROM chats WHERE uid=?", (uid,)).fetchall()
    return [r[0] for r in rows]


# =========================
# START
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚀 AdBot PRO++ Panel", reply_markup=panel())


# =========================
# BUTTONS
# =========================
async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    uid = q.from_user.id
    if uid not in ADMIN_IDS:
        return

    data = q.data

    if data == "login":
        states[uid] = "phone"
        await q.message.reply_text("Send phone with country code (+91...)")

    elif data == "accounts":
        if uid in clients:
            me = await clients[uid].get_me()
            await q.message.reply_text(f"Logged in: {me.first_name}")
        else:
            await q.message.reply_text("No account")

    elif data == "add":
        states[uid] = "add"
        await q.message.reply_text("Send chat id or @username")

    elif data == "remove":
        states[uid] = "remove"
        await q.message.reply_text("Send chat id to remove")

    elif data == "msg":
        states[uid] = "msg"
        await q.message.reply_text("Send ad message")

    elif data == "interval":
        states[uid] = "interval"
        await q.message.reply_text("Send seconds")

    elif data == "start":
        await start_ads(uid, q.message)

    elif data == "stop":
        await stop_ads(uid, q.message)


# =========================
# TEXT
# =========================
async def text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    msg = update.message.text

    state = states.get(uid)

    if uid not in ADMIN_IDS:
        return

    try:
        # LOGIN PHONE
        if state == "phone":
            client = TelegramClient(f"sessions/{uid}", API_ID, API_HASH)
            await client.connect()

            clients[uid] = client
            states[uid] = {"otp": msg}

            await client.send_code_request(msg)
            await update.message.reply_text("Enter OTP code")

        # LOGIN OTP
        elif isinstance(state, dict) and "otp" in state:
            phone = state["otp"]
            client = clients[uid]

            await client.sign_in(phone, msg)

            states[uid] = None
            await update.message.reply_text("✅ Logged in successfully")

        # ADD CHAT
        elif state == "add":
            cur.execute("INSERT INTO chats VALUES(?,?)", (uid, msg))
            db.commit()
            states[uid] = None
            await update.message.reply_text("Chat added")

        # REMOVE CHAT
        elif state == "remove":
            cur.execute("DELETE FROM chats WHERE uid=? AND chat=?", (uid, msg))
            db.commit()
            states[uid] = None
            await update.message.reply_text("Chat removed")

        # MESSAGE
        elif state == "msg":
            set_setting(uid, msg=msg)
            states[uid] = None
            await update.message.reply_text("Message saved")

        # INTERVAL
        elif state == "interval":
            set_setting(uid, interval=int(msg))
            states[uid] = None
            await update.message.reply_text("Interval saved")

        else:
            await update.message.reply_text("Use buttons", reply_markup=panel())

    except AuthRestartError:
        await update.message.reply_text("⚠ OTP failed. Try again.")
    except PhoneCodeInvalidError:
        await update.message.reply_text("❌ Wrong OTP")
    except SendCodeUnavailableError:
        await update.message.reply_text("⚠ Too many attempts. Wait few minutes.")
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")


# =========================
# ADS LOOP
# =========================
async def ads_loop(uid):
    while True:
        try:
            msg, interval = get_setting(uid)
            chats = get_chats(uid)

            if not msg or not chats:
                await asyncio.sleep(5)
                continue

            for c in chats:
                try:
                    await clients[uid].send_message(c, msg)
                except:
                    pass

            await asyncio.sleep(interval + random.randint(0, 5))

        except asyncio.CancelledError:
            break


async def start_ads(uid, message):
    if uid not in clients:
        await message.reply_text("Login first")
        return

    if uid in tasks:
        await message.reply_text("Already running")
        return

    tasks[uid] = asyncio.create_task(ads_loop(uid))
    await message.reply_text("Ads started")


async def stop_ads(uid, message):
    if uid in tasks:
        tasks[uid].cancel()
        del tasks[uid]
        await message.reply_text("Ads stopped")


# =========================
# MAIN (NO LOOP CRASH)
# =========================
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.TEXT, text))

    print("AdBot PRO running...")
    app.run_polling()
