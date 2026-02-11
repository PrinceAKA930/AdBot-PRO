import os
import json
import asyncio
from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from telethon import TelegramClient

# =========================================
# ENV (Railway safe)
# =========================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")

ADMIN_IDS = [
    int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()
]

# =========================================
# FILES
# =========================================

DATA_FILE = "data.json"
SESSION_DIR = "sessions"
os.makedirs(SESSION_DIR, exist_ok=True)

# =========================================
# DATABASE
# =========================================

def load_db():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE) as f:
        return json.load(f)

def save_db():
    with open(DATA_FILE, "w") as f:
        json.dump(db, f, indent=2)

db = load_db()

# =========================================
# USER DEFAULT
# =========================================

def get_user(uid):
    uid = str(uid)

    if uid not in db:
        db[uid] = {
            "chats": [],
            "interval": 60,
            "message": "🔥 Powered by Optima Ads Agency",
            "running": False,
            "state": None,
            "phone": None
        }
    return db[uid]

# =========================================
# TELETHON CLIENT
# =========================================

async def get_client(uid):
    return TelegramClient(f"{SESSION_DIR}/{uid}", API_ID, API_HASH)

# =========================================
# KEYBOARD
# =========================================

def keyboard():
    return ReplyKeyboardMarkup(
        [
            ["📱 Login", "🚪 Logout"],
            ["➕ Add Chat", "➖ Remove Chat"],
            ["📋 List Chats"],
            ["📝 Set Message"],
            ["⏱ Interval"],
            ["▶ Start Ads", "⏹ Stop Ads"],
            ["📊 Status"],
        ],
        resize_keyboard=True
    )

# =========================================
# ADS LOOP (REPEATED)
# =========================================

async def ads_loop(uid):
    user = get_user(uid)
    client = await get_client(uid)

    await client.connect()

    while user["running"]:
        try:
            for chat in user["chats"]:
                await client.send_message(chat, user["message"])

            await asyncio.sleep(user["interval"])

        except Exception:
            await asyncio.sleep(5)

    await client.disconnect()

# =========================================
# START
# =========================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 Optima Ads Agency Panel\nPremium Ad Automation Ready",
        reply_markup=keyboard()
    )

# =========================================
# MAIN HANDLER
# =========================================

async def text(update: Update, context: ContextTypes.DEFAULT_TYPE):

    msg = update.message.text.strip()
    uid = update.message.from_user.id
    user = get_user(uid)

    # ---------------- LOGIN ----------------

    if msg == "📱 Login":
        user["state"] = "phone"
        save_db()
        await update.message.reply_text("Send your phone number (+91xxxx)")
        return

    if user["state"] == "phone":
        user["phone"] = msg

        client = await get_client(uid)
        await client.connect()
        await client.send_code_request(msg)

        user["state"] = "otp"
        save_db()

        await update.message.reply_text("Send OTP like: code12345")
        return

    if user["state"] == "otp":
        if not msg.startswith("code"):
            await update.message.reply_text("Format: code12345")
            return

        code = msg[4:]

        client = await get_client(uid)
        await client.connect()
        await client.sign_in(user["phone"], code)

        user["state"] = None
        save_db()

        await update.message.reply_text("✅ Login successful")
        return

    # ---------------- LOGOUT ----------------

    if msg == "🚪 Logout":
        session = f"{SESSION_DIR}/{uid}.session"
        if os.path.exists(session):
            os.remove(session)

        await update.message.reply_text("Logged out")
        return

    # ---------------- MESSAGE ----------------

    if msg == "📝 Set Message":
        user["state"] = "setmsg"
        await update.message.reply_text("Send new ad message")
        return

    if user["state"] == "setmsg":
        user["message"] = msg
        user["state"] = None
        save_db()
        await update.message.reply_text("✅ Message updated")
        return

    # ---------------- CHATS ----------------

    if msg == "➕ Add Chat":
        user["state"] = "addchat"
        await update.message.reply_text("Send @username or chat id")
        return

    if msg == "➖ Remove Chat":
        user["state"] = "removechat"
        await update.message.reply_text("Send chat id to remove")
        return

    if msg == "📋 List Chats":
        await update.message.reply_text("\n".join(user["chats"]) or "No chats")
        return

    if user["state"] == "addchat":
        user["chats"].append(msg)
        user["state"] = None
        save_db()
        await update.message.reply_text("Added")
        return

    if user["state"] == "removechat":
        if msg in user["chats"]:
            user["chats"].remove(msg)
        user["state"] = None
        save_db()
        await update.message.reply_text("Removed")
        return

    # ---------------- INTERVAL ----------------

    if msg == "⏱ Interval":
        user["state"] = "interval"
        await update.message.reply_text("Send seconds")
        return

    if user["state"] == "interval":
        user["interval"] = int(msg)
        user["state"] = None
        save_db()
        await update.message.reply_text("Interval updated")
        return

    # ---------------- ADS ----------------

    if msg == "▶ Start Ads":
        if not user["chats"]:
            await update.message.reply_text("Add chats first")
            return

        user["running"] = True
        save_db()

        context.application.create_task(ads_loop(uid))

        await update.message.reply_text("🚀 Ads started")
        return

    if msg == "⏹ Stop Ads":
        user["running"] = False
        save_db()
        await update.message.reply_text("Stopped")
        return

    # ---------------- STATUS ----------------

    if msg == "📊 Status":
        await update.message.reply_text(
            f"Chats: {len(user['chats'])}\n"
            f"Interval: {user['interval']}s\n"
            f"Running: {user['running']}"
        )

# =========================================
# MAIN
# =========================================

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT, text))

    print("🚀 Optima Ads Agency running...")
    app.run_polling()

if __name__ == "__main__":
    main()
