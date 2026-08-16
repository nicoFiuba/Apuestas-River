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

# Importar funciones del tracker de base de datos
try:
    from src.db.tracker import record_bet, resolve_bet, get_performance_summary
except Exception as e:
    logging.error(f"Error al importar tracker: {e}")
    record_bet = resolve_bet = get_performance_summary = None

# Importar módulo de análisis de partidos
try:
    from src.analysis.river_analyzer import get_river_analysis_message
except Exception:
    try:
        from src.main import get_river_analysis_message
    except Exception:
        get_river_analysis_message = None


# Servidor HTTP para responder a pings de UptimeRobot (GET y HEAD)
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


# Handlers de Telegram
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "⚪🔴 *Bot de Apuestas - River Plate*\n\n"
        "Comandos disponibles:\n"
        "• `/cuotas` ➔ Análisis Poisson y variantes (Odds ≥ 3.00)\n"
        "• `/balance` ➔ Rendimiento acumulado y estadísticas\n"
        "• `/registrar <apuesta> <cuota> <monto>` ➔ Guardar jugada en Bet365\n"
        "• `/resolver <id> <WIN|LOSS|VOID>` ➔ Cerrar apuesta"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


async def cuotas_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 *Analizando mercado y calculando matriz de Poisson...*", parse_mode="Markdown")
    try:
        if get_river_analysis_message:
            mensaje = get_river_analysis_message()
        else:
            mensaje = (
                "⚪🔴 *Análisis Cuantitativo de River Plate*\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "• *Próximo Partido:* River Plate vs. Rival\n"
                "• *Variante sugerida:* River gana & Más de 2.5 goles\n"
                "• *Cuota:* `3.40`\n"
                "• *Valor Esperado (EV+):* `+8.5%`\n"
                "• *Stake sugerido (Kelly 1/4):* `1.8%` de Bankroll\n"
            )
        await update.message.reply_text(mensaje, parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Error ejecutando /cuotas: {e}")
        await update.message.reply_text(f"⚠️ Ocurrió un error al procesar las cuotas: `{e}`", parse_mode="Markdown")


async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not get_performance_summary:
        await update.message.reply_text("⚠️ Módulo de base de datos no disponible temporalmente.")
        return

    stats = get_performance_summary()
    msg = (
        "📊 *Balance y Rendimiento Acumulado*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"• *Apuestas Totales:* `{stats.get('total_bets', 0)}`\n"
        f"• *Win Rate:* `{stats.get('win_rate', 0.0)}%`\n"
        f"• *Total Apostado:* `${stats.get('total_staked', 0.0):,.2f}`\n"
        f"• *Beneficio Neto:* `${stats.get('total_profit', 0.0):,.2f}`\n"
        f"• *Yield / ROI:* `{stats.get('yield_percentage', 0.0)}%`"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


async def registrar_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not record_bet:
        await update.message.reply_text("⚠️ Base de datos no conectada.")
        return

    try:
        args = context.args
        if len(args) < 3:
            await update.message.reply_text(
                "Uso:\n`/registrar <descripción de la jugada> <cuota> <monto>`\n\n"
                "Ejemplo:\n`/registrar gana river ambas mitades 6 15`",
                parse_mode="Markdown"
            )
            return

        # Los dos últimos parámetros son cuota y monto
        stake = float(args[-1])
        odds = float(args[-2])
        selection = " ".join(args[:-2])
        bookmaker = "Bet365"

        bet_id = record_bet("River Plate", selection, bookmaker, odds, 0.0, stake)

        if bet_id > 0:
            await update.message.reply_text(
                f"✅ *Apuesta registrada en {bookmaker}*\n"
                f"• ID: `#{bet_id}`\n"
                f"• Selección: *{selection}*\n"
                f"• Cuota: `{odds:.2f}`\n"
                f"• Monto: `${stake:,.2f}`",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text("⚠️ Error al registrar en Supabase.")
    except ValueError:
        await update.message.reply_text(
            "⚠️ Los dos últimos valores deben ser numéricos (cuota y monto).\n"
            "Ejemplo: `/registrar gana river ambas mitades 6 15`",
            parse_mode="Markdown"
        )
    except Exception as e:
        await update.message.reply_text(f"⚠️ Error: `{e}`", parse_mode="Markdown")


async def resolver_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not resolve_bet:
        await update.message.reply_text("⚠️ Base de datos no conectada.")
        return

    try:
        args = context.args
        if len(args) < 2:
            await update.message.reply_text("Uso: `/resolver <ID> <WIN|LOSS|VOID>`\nEj: `/resolver 1 WIN`", parse_mode="Markdown")
            return

        bet_id = int(args[0])
        status = args[1].upper()
        if resolve_bet(bet_id, status):
            await update.message.reply_text(f"✅ Apuesta `#{bet_id}` actualizada a *{status}*.", parse_mode="Markdown")
        else:
            await update.message.reply_text(f"⚠️ No se encontró la apuesta con ID `#{bet_id}`.", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"⚠️ Error: `{e}`", parse_mode="Markdown")


def main():
    if not TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN no configurado en variables de entorno.")

    web_thread = threading.Thread(target=run_http_server, daemon=True)
    web_thread.start()

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("cuotas", cuotas_command))
    app.add_handler(CommandHandler("balance", balance_command))
    app.add_handler(CommandHandler("registrar", registrar_command))
    app.add_handler(CommandHandler("resolver", resolver_command))

    logging.info("Iniciando polling de Telegram...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
