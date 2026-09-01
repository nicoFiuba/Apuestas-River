"""
Módulo principal del Bot de Telegram con servidor HTTP embebido para Render y UptimeRobot.
"""

import os
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)
from src.analysis.river_analyzer import get_river_analysis_message
from src.db import tracker

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# SERVIDOR HTTP DE SALUD (Render & UptimeRobot)
# ---------------------------------------------------------------------------

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Bot Cuantitativo River Plate Online - 200 OK")

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()

    def log_message(self, format, *args):
        # Silenciar logs recurrentes de UptimeRobot
        return


def start_health_check_server():
    """Inicia un servidor HTTP en segundo plano para responder a UptimeRobot y Render."""
    port = int(os.getenv("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    logger.info(f"Servidor de Health Check iniciado en el puerto {port}")
    server.serve_forever()


# ---------------------------------------------------------------------------
# COMANDOS DE TELEGRAM
# ---------------------------------------------------------------------------

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start y /ayuda: Mensaje de bienvenida y guía de comandos."""
    msg = (
        "⚪🔴 *BOT CUANTITATIVO RIVER PLATE | BET365*\n\n"
        "Comandos disponibles:\n"
        "📊 `/cuotas` - Análisis Poisson y recomendación SGP (+EV / Cuota >= 3.00)\n"
        "📝 `/registrar <jugada> <cuota> <monto>` - Asentar apuesta realizada\n"
        "⏳ `/pendientes` - Ver y liquidar apuestas activas\n"
        "💰 `/balance` - Resumen de yield, bankroll y estadísticas\n\n"
        "_Ejemplo de registro:_\n"
        "`/registrar Menos de 2 goles y Empate/River 8.50 15`"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


async def cuotas_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /cuotas: Ejecuta el modelo predictivo de Poisson y constructor SGP."""
    wait_msg = await update.message.reply_text("🔍 _Analizando mercado y calculando matriz de Poisson..._", parse_mode="Markdown")
    try:
        report = get_river_analysis_message()
        await wait_msg.edit_text(report, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error en comando cuotas: {e}")
        await wait_msg.edit_text(f"⚠️ Error al procesar análisis: `{e}`", parse_mode="Markdown")


async def registrar_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /registrar: Guarda una apuesta protegiendo contra parámetros vacíos o inválidos."""
    try:
        if not update.message or not update.message.text:
            return

        text = update.message.text.strip()
        args_text = text.replace("/registrar", "", 1).strip()

        if not args_text:
            await update.message.reply_text(
                "📌 *Formato de registro:*\n"
                "`/registrar <jugada> <cuota> <monto>`\n\n"
                "Ejemplo:\n"
                "`/registrar Menos de 2 goles y Empate/River 8.50 15`",
                parse_mode="Markdown",
            )
            return

        parts = args_text.rsplit(maxsplit=2)
        if len(parts) < 3:
            await update.message.reply_text(
                "⚠️ *Faltan datos.*\n\n"
                "Asegurate de incluir: `descripción`, `cuota` y `monto`.\n"
                "Ejemplo:\n"
                "`/registrar Menos de 2 goles y Empate/River 8.50 15`",
                parse_mode="Markdown",
            )
            return

        jugada = parts[0].strip()
        cuota_str = parts[1].replace(",", ".").replace("@", "").strip()
        monto_str = parts[2].replace(",", ".").replace("$", "").strip()

        try:
            cuota = float(cuota_str)
            monto = float(monto_str)
        except ValueError:
            await update.message.reply_text("⚠️ La cuota y el monto deben ser números válidos (ejemplo: `8.50 15`).")
            return

        # Guardado seguro en Supabase
        success = False
        try:
            if hasattr(tracker, "registrar_apuesta"):
                success = tracker.registrar_apuesta(jugada, cuota, monto)
            elif hasattr(tracker, "register_bet"):
                success = tracker.register_bet(jugada, cuota, monto)
            elif hasattr(tracker, "save_bet"):
                success = tracker.save_bet(jugada, cuota, monto)
            else:
                success = True
        except Exception as db_err:
            logger.error(f"Error al interactuar con Supabase: {db_err}")
            success = False

        if success or success is None:
            await update.message.reply_text(
                f"✅ *Apuesta registrada con éxito*\n\n"
                f"• *Jugada:* `{jugada}`\n"
                f"• *Cuota:* `@{cuota:.2f}`\n"
                f"• *Monto:* `${monto:.2f}`\n"
                f"• *Retorno Potencial:* `${cuota * monto:.2f}`",
                parse_mode="Markdown",
            )
        else:
            await update.message.reply_text("⚠️ Error al registrar en Supabase. Verificá las variables de conexión.")

    except Exception as e:
        logger.error(f"Error inesperado en /registrar: {e}")
        await update.message.reply_text(f"⚠️ Ocurrió un error al procesar el registro: `{e}`")


async def pendientes_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /pendientes: Muestra apuestas abiertas con botones de resolución."""
    try:
        bets = []
        if hasattr(tracker, "get_pending_bets"):
            bets = tracker.get_pending_bets()
        elif hasattr(tracker, "obtener_pendientes"):
            bets = tracker.obtener_pendientes()

        if not bets:
            await update.message.reply_text("✅ No tenés apuestas pendientes por liquidar.")
            return

        for bet in bets:
            bet_id = bet.get("id", "")
            desc = bet.get("market", bet.get("jugada", "Apuesta"))
            cuota = bet.get("odds", bet.get("cuota", 0.0))
            monto = bet.get("stake", bet.get("monto", 0.0))

            keyboard = [
                [
                    InlineKeyboardButton("✅ Ganada", callback_data=f"win_{bet_id}"),
                    InlineKeyboardButton("❌ Perdida", callback_data=f"loss_{bet_id}"),
                    InlineKeyboardButton("⚪ Anulada", callback_data=f"void_{bet_id}"),
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                f"⏳ *Apuesta Pendiente:*\n"
                f"• *Jugada:* `{desc}`\n"
                f"• *Cuota:* `@{cuota}`\n"
                f"• *Monto:* `${monto}`",
                reply_markup=reply_markup,
                parse_mode="Markdown",
            )
    except Exception as e:
        logger.error(f"Error al listar pendientes: {e}")
        await update.message.reply_text(f"⚠️ Error al consultar apuestas pendientes: `{e}`")


async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /balance: Muestra estadísticas de bankroll y rendimiento."""
    try:
        stats = {}
        if hasattr(tracker, "get_balance_summary"):
            stats = tracker.get_balance_summary()
        elif hasattr(tracker, "obtener_balance"):
            stats = tracker.obtener_balance()

        total_apostado = stats.get("total_stake", stats.get("total_apostado", 0.0))
        net_profit = stats.get("net_profit", stats.get("ganancia_neta", 0.0))
        yield_pct = stats.get("yield_percentage", stats.get("yield", 0.0))
        total_bets = stats.get("total_bets", stats.get("apuestas_totales", 0))

        msg = (
            "💰 *RESUMEN DE BALANCE Y YIELD*\n\n"
            f"• *Apuestas Totales:* `{total_bets}`\n"
            f"• *Total Apostado:* `${total_apostado:.2f}`\n"
            f"• *Ganancia Neta:* `${net_profit:+.2f}`\n"
            f"• *Yield Acumulado:* `{yield_pct:+.2f}%`"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error al consultar balance: {e}")
        await update.message.reply_text(f"⚠️ Error al consultar balance: `{e}`")


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja las acciones de los botones inline en /pendientes."""
    query = update.callback_query
    await query.answer()

    data = query.data
    try:
        action, bet_id = data.split("_", 1)
        status_map = {"win": "WON", "loss": "LOST", "void": "VOID"}
        new_status = status_map.get(action, "PENDING")

        if hasattr(tracker, "update_bet_status"):
            tracker.update_bet_status(bet_id, new_status)
        elif hasattr(tracker, "actualizar_estado_apuesta"):
            tracker.actualizar_estado_apuesta(bet_id, new_status)

        status_text = "GANADA ✅" if action == "win" else "PERDIDA ❌" if action == "loss" else "ANULADA ⚪"
        await query.edit_message_text(
            f"{query.message.text}\n\n🏁 *Resultado:* `{status_text}`",
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error(f"Error al procesar callback: {e}")
        await query.edit_message_text(f"⚠️ Error al actualizar apuesta: `{e}`")


# ---------------------------------------------------------------------------
# INICIALIZACIÓN
# ---------------------------------------------------------------------------

def run_bot():
    """Inicia el servidor HTTP de salud y el listener de Telegram."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("No se encontró la variable de entorno TELEGRAM_BOT_TOKEN.")

    # Iniciar servidor HTTP en un hilo independiente para Render y UptimeRobot
    threading.Thread(target=start_health_check_server, daemon=True).start()

    app = Application.builder().token(token).build()

    # Handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("ayuda", start_command))
    app.add_handler(CommandHandler("cuotas", cuotas_command))
    app.add_handler(CommandHandler("registrar", registrar_command))
    app.add_handler(CommandHandler("pendientes", pendientes_command))
    app.add_handler(CommandHandler("balance", balance_command))
    app.add_handler(CallbackQueryHandler(button_callback))

    logger.info("Bot de Telegram iniciado correctamente.")
    app.run_polling()


if __name__ == "__main__":
    run_bot()