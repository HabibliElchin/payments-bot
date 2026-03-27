import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    ContextTypes,
    CommandHandler,
)
import os
import json
from zoneinfo import ZoneInfo

TOKEN = os.getenv("TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID"))  # сюда идут автоматические сообщения

BAKU_TZ = ZoneInfo("Asia/Baku")


def get_now():
    return datetime.datetime.now(BAKU_TZ)


scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]

creds_dict = json.loads(os.getenv("GOOGLE_CREDS"))
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)
sheet = client.open("Payments").sheet1


async def send_today_payments(context, chat_id):
    today = get_now().day
    rows = sheet.get_all_records()

    found = False

    for i, row in enumerate(rows, start=2):
        try:
            day = int(float(row["День оплаты"]))
        except Exception:
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
                reply_markup=InlineKeyboardMarkup(keyboard),
            )

    if not found:
        await context.bot.send_message(
            chat_id=chat_id,
            text="Сегодня никто не должен платить 👍",
        )


async def daily_job(context: ContextTypes.DEFAULT_TYPE):
    await send_today_payments(context, CHAT_ID)


async def today_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_today_payments(context, update.effective_chat.id)


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


async def income_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = sheet.get_all_records()
    total = 0

    for row in rows:
        if row["Статус"] == "paid":
            try:
                total += int(float(row["Сумма"]))
            except Exception:
                pass

    await update.message.reply_text(f"💰 Доход: {total}₼")


async def reset_month(context: ContextTypes.DEFAULT_TYPE):
    rows = sheet.get_all_records()

    for i, _row in enumerate(rows, start=2):
        sheet.update_cell(i, 6, "pending")

    await context.bot.send_message(
        chat_id=CHAT_ID,
        text="🔄 Новый месяц — все статусы сброшены",
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
app.add_handler(CommandHandler("today", today_command))
app.add_handler(CommandHandler("debts", debts_command))
app.add_handler(CommandHandler("income", income_command))

# Авто-уведомление каждый день в 09:00 по Баку
app.job_queue.run_daily(
    daily_job,
    time=datetime.time(hour=9, minute=0, tzinfo=BAKU_TZ),
    name="daily_payments",
)

# Сброс 1 числа каждого месяца в 00:01 по Баку
app.job_queue.run_monthly(
    reset_month,
    when=datetime.time(hour=0, minute=1, tzinfo=BAKU_TZ),
    day=1,
    name="monthly_reset",
)

app.run_polling()
