import os
import logging
import httpx
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


async def send_telegram_alert(message: str) -> bool:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id or token.startswith("tu_"):
        logging.warning("TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID no configurados en el archivo .env")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            logging.info("🚀 Alerta enviada con éxito a Telegram!")
            return True
    except Exception as e:
        logging.error(f"Error al enviar mensaje por Telegram: {e}")
        return False
