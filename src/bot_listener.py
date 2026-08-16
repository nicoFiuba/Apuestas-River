import os
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
PORT = int(os.getenv("PORT", "10000"))


class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Bot cuantitativo de River Plate OK")

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()

    def log_message(self, format, *args):
        return


def run_http_server():
    server = HTTPServer(("0.0.0.0", PORT), HealthCheckHandler)
    logging.info(f"Servidor HTTP activo en el puerto {PORT}")
    server.serve_forever()


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 *Bot de Apuestas River Plate activo.* Usá `/cuotas` para analizar partidos.", parse_mode="Markdown")


def main():
    if not TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN no configurado en variables de entorno.")

    web_thread = threading.Thread(target=run_http_server, daemon=True)
    web_thread.start()

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))

    try:
        from src.main import register_handlers
        register_handlers(app)
    except Exception:
        pass

    logging.info("Iniciando polling de Telegram...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
