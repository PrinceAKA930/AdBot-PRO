import os
import asyncio
import json
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from telethon import TelegramClient

# =============================
# ENV
# =============================

BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x]

# =============================
# DATA
# =============================

DATA_FILE = "data.json"


def load():
    if not os.path.exists(DATA_FILE):
        return {"chats": [], "message": "", "interval": 60}
    return json.load(open(DATA_FILE))


def save(data):
    json.dump(data, open(DATA_FILE, "w"), indent=2)


data = load()

# =============================
# TELETHON
# =============================

client = TelegramClient("session", API_ID, API_HASH)

phone_cache = {}

# =============================
# UI
# =============================


def menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔐 Login", callback_data="login")],
        [InlineKeyboardButton("➕ Add Chat", callback_data="add"),
         InlineKeyboardButton("➖ Remove Chat", callback_data="remove")],
        [InlineKeyboardButton("📝 Set Message", callback_data="msg")],
        [InlineKeyboardButton("⏱ Set Interval", callback_data="interval")],
        [InlineKeyboardButton("▶ Start Ads", callback_data="start"),
         InlineKeyboardButton("⏹ Stop Ads", callback_data="stop")],
    ])


# =============================
# START
# =============================


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return

    await update.message.reply_text(
        "🚀 **Optima Agency Ads Panel**\n\nPremium Telegram Automation",
        reply_markup=menu(),
        parse_mode="Markdown"
    )


# =============================
# BUTTON HANDLER
# =============================


async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    action = q.data

    if action == "login":
        context.user_data["state"] = "phone"
        await q.message.reply_text("📱 Send your mobile number with country code\nExample: +919876543210")

    elif action == "add":
        context.user_data["state"] = "add"
        await q.message.reply_text("Send chat ID or @username")

    elif action == "remove":
        context.user_data["state"] = "remove"
        await q.message.reply_text("Send chat to remove")

    elif action == "msg":
        context.user_data["state"] = "msg"
        await q.message.reply_text("Send your ad message")

    elif action == "interval":
        context.user_data["state"] = "interval"
        await q.message.reply_text("Send interval in seconds")

    elif action == "start":
        context.application.create_task(ad_loop(context))
        await q.message.reply_text("▶ Ads started")

    elif action == "stop":
        context.application.stop_ads = True
        await q.message.reply_text("⏹ Ads stopped")


# =============================
# TEXT INPUT
# =============================


async def text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return

    state = context.user_data.get("state")
    msg = update.message.text

    # LOGIN FLOW
    if state == "phone":
        await client.connect()
        phone_cache["phone"] = msg
        await client.send_code_request(msg)
        context.user_data["state"] = "otp"
        await update.message.reply_text("Enter OTP like code12345")

    elif state == "otp":
        code = msg.replace("code", "")
        await client.sign_in(phone_cache["phone"], code)
        await update.message.reply_text("✅ Logged in successfully")
        context.user_data["state"] = None

    # ADD CHAT
    elif state == "add":
        data["chats"].append(msg)
        save(data)
        await update.message.reply_text("Chat added")
        context.user_data["state"] = None

    # REMOVE CHAT
    elif state == "remove":
        if msg in data["chats"]:
            data["chats"].remove(msg)
            save(data)
        await update.message.reply_text("Chat removed")
        context.user_data["state"] = None

    # MESSAGE
    elif state == "msg":
        data["message"] = msg
        save(data)
        await update.message.reply_text("Message saved")
        context.user_data["state"] = None

    # INTERVAL
    elif state == "interval":
        data["interval"] = int(msg)
        save(data)
        await update.message.reply_text("Interval updated")
        context.user_data["state"] = None


# =============================
# AD LOOP
# =============================


async def ad_loop(context):
    context.application.stop_ads = False

    while not context.application.stop_ads:
        for chat in data["chats"]:
            try:
                await context.bot.send_message(chat, data["message"])
            except:
                pass

        await asyncio.sleep(data["interval"])


# =============================
# MAIN
# =============================


def main():
    print("🚀 Optima Agency Bot running...")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text))

    app.run_polling()


if __name__ == "__main__":
    main()
