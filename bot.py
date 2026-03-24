import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    ContextTypes,
    CommandHandler
)
import os
import json

TOKEN = os.getenv("TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID"))  # используется только для авто-уведомлений

# 🌍 timezone (Азербайджан UTC+4)
def get_now():
    return datetime.datetime.utcnow() + datetime.timedelta(hours=4)

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

creds_dict = json.loads(os.getenv("GOOGLE_CREDS"))
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)
sheet = client.open("Payments").sheet1


# 🔔 отправка платежей
async def send_today_payments(context, chat_id):
    today = get_now().day
    rows = sheet.get_all_records()

    found = False

    for i, row in enumerate(rows, start=2):
        try:
            day = int(float(row["День оплаты"]))
        except:
            continue

        if day == today and row["Статус"] != "paid":
            found = True

            text = f"{row['Имя']} — {row['Сумма']}₼"

            keyboard = [[
                InlineKeyboardButton("✅ Оплатил", callback_data=f"paid_{i}"),
                InlineKeyboardButton("❌ Не оплатил", callback_data=f"no_{i}")
            ]]

            await context.bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

    if not found:
        await context.bot.send_message(
            chat_id=chat_id,
            text="Сегодня никто не должен платить 👍"
        )


# ⏰ ежедневка (идёт в заданный CHAT_ID — например группа)
async def daily_job(context: ContextTypes.DEFAULT_TYPE):
    await send_today_payments(context, CHAT_ID)


# 📅 /today (отвечает туда где вызвали)
async def today_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await send_today_payments(context, chat_id)


# 📊 /debts
async def debts_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = sheet.get_all_records()

    text = "❗ Должники:\n\n"
    found = False

    for row in rows:
        if row["Статус"] != "paid":
            found = True
            text += f"{row['Имя']} — {row['Сумма']}₼\n"

    if not found:
        text = "Все оплатили 👍"

    await update.message.reply_text(text)


# 💰 /income
async def income_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = sheet.get_all_records()

    total = 0

    for row in rows:
        if row["Статус"] == "paid":
            try:
                total += int(float(row["Сумма"]))
            except:
                pass

    await update.message.reply_text(f"💰 Доход: {total}₼")


# 🔁 сброс месяца
async def reset_month(context: ContextTypes.DEFAULT_TYPE):
    rows = sheet.get_all_records()

    for i, row in enumerate(rows, start=2):
        sheet.update_cell(i, 6, "pending")

    await context.bot.send_message(
        chat_id=CHAT_ID,
        text="🔄 Новый месяц — все статусы сброшены"
    )


# ✅ кнопки
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


# 🚀 запуск
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CallbackQueryHandler(button_handler))
app.add_handler(CommandHandler("today", today_command))
app.add_handler(CommandHandler("debts", debts_command))
app.add_handler(CommandHandler("income", income_command))

# ежедневные уведомления
app.job_queue.run_daily(
    daily_job,
    time=datetime.time(hour=9, minute=0)
)

# сброс 1 числа
app.job_queue.run_monthly(
    reset_month,
    when=datetime.time(hour=0, minute=1),
    day=1
)

app.run_polling()
