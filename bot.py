import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CallbackQueryHandler, ContextTypes
import os

TOKEN = os.getenv("TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID"))

scope = ["https://spreadsheets.google.com/feeds",
         "https://www.googleapis.com/auth/drive"]

import json

creds_dict = json.loads(os.getenv("GOOGLE_CREDS"))
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)
sheet = client.open("Payments").sheet1

async def send_notifications(app):
    today = datetime.datetime.now().day
    rows = sheet.get_all_records()

    for i, row in enumerate(rows, start=2):
        if row["День оплаты"] == today and row["Статус"] != "paid":
            text = f"{row['Имя']} — {row['Сумма']}₼"

            keyboard = [[
                InlineKeyboardButton("✅ Оплатил", callback_data=f"paid_{i}"),
                InlineKeyboardButton("❌ Не оплатил", callback_data=f"no_{i}")
            ]]

            await app.bot.send_message(
                chat_id=CHAT_ID,
                text=text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    action, row = query.data.split("_")
    row = int(row)

    if action == "paid":
        sheet.update_cell(row, 6, "paid")
        await query.edit_message_text("✅ Оплачено")
    else:
        await query.edit_message_text("❌ Не оплачено")

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CallbackQueryHandler(button_handler))
app.job_queue.run_daily(send_notifications, time=datetime.time(hour=9, minute=0))

app.run_polling()
