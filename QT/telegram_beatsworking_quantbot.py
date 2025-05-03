import asyncio
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

# http://t.me/BeatsWorking_QuantBot
token = '7022978232:AAFWMxyQFdG1udPxM6gCYhHtchqHsyBYJyA'

# async def main():
#     bot = telegram.Bot(token)
#     async with bot:
#         # print(await bot.get_me())
#         updates = (await bot.get_updates())[2]
#         print(updates)


# if __name__ == '__main__':
#     asyncio.run(main())



logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# "NQ-ES-YM Weekly Cycle (H1) - ↓ Seq-SMT (NQ↗ ES↘ YM↘)" 
# "NQ-ES-YM Daily Cycle (M15) - ↑ Seq-SMT (NQ↗ ES↘ YM↘)"
# "NQ-ES-YM Session Cycle (M5) - ↑ Seq-SMT (NQ↗ ES↘ YM↘)"
# "NQ-ES-YM Micro Cycle (M1) - ↑ Seq-SMT (NQ↗ ES↘ YM↘)"

# "NQ-ES-YM Weekly Cycle (H1) - ↓ PSP (NQ↗ ES↘ YM↘)" 
# "NQ-ES-YM Daily Cycle (M15) - ↑ PSP (NQ↗ ES↘ YM↘)"
# "NQ-ES-YM Session Cycle (M5) - ↑ PSP (NQ↗ ES↘ YM↘)"
# "NQ-ES-YM Micro Cycle (M1) - ↑ PSP (NQ↗ ES↘ YM↘)"
# Long = &#x2B08;
# Short = &#x2B0A;

# "⬆ NQ-ES-YM\nWeekly Cycle (H1): Seq-SMT (NQ⬈ ES⬊ YM⬈)\nSession Cycle (M15): PSP 09:45 (NQ⬈ ES⬊ YM⬈)"

# f"{signal.asset1.Name}-{signal.asset2.Name}-{signal.asset3.Name} {signal.cycle.name} Cycle (signal.cycle.tf) - {signal.direction_glyph} {signal.name} ({signal.asset1.Name}{signal.asset1.direction_glyph} {signal.asset2.Name}{signal.asset2.direction_glyph} {signal.asset2.Name}{signal.asset2.direction_glyph})"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="hi...")

async def signal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="NQ-ES-YM Weekly Cycle (H1) - ⬆ Seq-SMT (NQ⬈ ES↘ YM➚)")

async def callback_minute(context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id='1876614647', text="⬆ NQ-ES-YM\nNQ⬈ ES⬊ YM⬈ SMT H1 \nNQ⬈ ES⬊ YM⬈ PSP M15 09:45")



if __name__ == '__main__':
    application = ApplicationBuilder().token(token).build()
    job_queue = application.job_queue

    start_handler = CommandHandler('start', start)
    application.add_handler(start_handler)

    signal_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), signal)
    application.add_handler(signal_handler)

    job_minute = job_queue.run_repeating(callback_minute, interval=20, first=10)

    application.run_polling()