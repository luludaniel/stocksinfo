import asyncio
import telegram
from telegram.constants import ParseMode
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

MAX_MSG_LEN = 4096


async def _send_async(text: str):
    bot = telegram.Bot(token=TELEGRAM_BOT_TOKEN)
    chunks = [text[i:i + MAX_MSG_LEN] for i in range(0, len(text), MAX_MSG_LEN)]
    for chunk in chunks:
        try:
            await bot.send_message(
                chat_id=TELEGRAM_CHAT_ID,
                text=chunk,
                parse_mode=ParseMode.MARKDOWN,
            )
        except telegram.error.BadRequest:
            # Markdown 파싱 실패 시 plain text로 재전송
            await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=chunk)


def send(text: str):
    asyncio.run(_send_async(text))


def send_error(error: str):
    send(f"⚠️ *StocksInfo 오류*\n```\n{error[:500]}\n```")
