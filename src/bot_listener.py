"""
Módulo principal del Bot de Telegram conectado con src.db.tracker y servidor HTTP de salud.
"""

import os
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)
from src.analysis.river_analyzer import get_river_analysis_message
from src.db.tracker import (
    record_bet,
    resolve_bet,
    get_pending_bets,
    get_performance_summary,
)

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
        return


def start_health_check_server():
    """Inicia servidor en background para Render."""
    port = int(os.getenv("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    logger.info(f"Servidor de Health Check iniciado en el puerto {port}")
    server.serve_forever()


# ---------------------------------------------------------------------------
# HANDLERS DE COMANDOS
# ---------------------------------------------------------------------------

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Guía de comandos disponibles."""
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
    """Ejecuta el cálculo Poisson y constructor SGP."""
    wait_msg = await update.message.reply_text("🔍 _Analizando mercado y calculando matriz de Poisson..._", parse_mode="Markdown")
    try:
        report = get_river_analysis_message()
        await wait_msg.edit_text(report, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error en comando cuotas: {e}")
        await wait_msg.edit_text(f"⚠️ Error al procesar análisis: `{e}`", parse_mode="Markdown")


async def registrar_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Guarda la apuesta usando record_bet de tracker.py."""
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

        # Inserción en Supabase / PostgreSQL con record_bet
        try:
            bet_id = record_bet(
                match_name="River Plate vs. Rival",
                selection=jugada,
                bookmaker="Bet365",
                odds=cuota,
                ev_percentage=0.0,
                stake_ars=monto,
            )
            success = bool(bet_id)
        except Exception as db_err:
            logger.error(f"Error en record_bet: {db_err}")
            success = False

        if success:
            await update.message.reply_text(
                f"✅ *Apuesta registrada con éxito (ID: #{bet_id})*\n\n"
                f"• *Jugada:* `{jugada}`\n"
                f"• *Cuota:* `@{cuota:.2f}`\n"
                f"• *Monto:* `${monto:.2f}`\n"
                f"• *Retorno Potencial:* `${cuota * monto:.2f}`",
                parse_mode="Markdown",
            )
        else:
            await update.message.reply_text("⚠️ Error al registrar en la base de datos.")

    except Exception as e:
        logger.error(f"Error inesperado en /registrar: {e}")
        await update.message.reply_text(f"⚠️ Ocurrió un error al procesar el registro: `{e}`")


async def pendientes_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra apuestas pendientes con botones de resolución (resolve_bet)."""
    try:
        bets = get_pending_bets()
        if not bets:
            await update.message.reply_text("✅ No tenés apuestas pendientes por liquidar.")
            return

        for bet in bets:
            # Compatibilidad con dict o tuple
            if isinstance(bet, dict):
                b_id = bet.get("id")
                desc = bet.get("selection", bet.get("market_name", "Apuesta"))
                cuota = bet.get("odds", 0.0)
                monto = bet.get("stake_ars", bet.get("stake", 0.0))
            else:
                b_id, desc, cuota, monto = bet[0], bet[2], bet[4], bet[6]

            keyboard = [
                [
                    InlineKeyboardButton("✅ Ganada", callback_data=f"win_{b_id}"),
                    InlineKeyboardButton("❌ Perdida", callback_data=f"loss_{b_id}"),
                    InlineKeyboardButton("⚪ Anulada", callback_data=f"void_{b_id}"),
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                f"⏳ *Apuesta Pendiente (#{b_id}):*\n"
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
    """Muestra el historial consolidado usando get_performance_summary."""
    try:
        stats = get_performance_summary()

        total_bets = stats.get("total_bets", 0)
        total_staked = stats.get("total_staked", stats.get("total_stake", 0.0))
        net_profit = stats.get("net_profit", 0.0)
        yield_pct = stats.get("yield_pct", stats.get("yield_percentage", 0.0))
        win_rate = stats.get("win_rate", 0.0)

        msg = (
            "💰 *RESUMEN DE BALANCE Y HISTORIAL*\n\n"
            f"• *Apuestas Totales:* `{total_bets}`\n"
            f"• *Total Apostado:* `${total_staked:.2f}`\n"
            f"• *Ganancia Neta:* `${net_profit:+.2f}`\n"
            f"• *Yield Acumulado:* `{yield_pct:+.2f}%`\n"
            f"• *Win Rate:* `{win_rate:.1f}%`"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error al consultar balance: {e}")
        await update.message.reply_text(f"⚠️ Error al consultar balance: `{e}`")


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Procesa el cierre de una apuesta con resolve_bet."""
    query = update.callback_query
    await query.answer()

    data = query.data
    try:
        action, bet_id_str = data.split("_", 1)
        bet_id = int(bet_id_str)
        status_map = {"win": "WON", "loss": "LOST", "void": "VOID"}
        new_status = status_map.get(action, "PENDING")

        success = resolve_bet(bet_id, new_status)

        if success:
            status_text = "GANADA ✅" if action == "win" else "PERDIDA ❌" if action == "loss" else "ANULADA ⚪"
            await query.edit_message_text(
                f"{query.message.text}\n\n🏁 *Resultado:* `{status_text}`",
                parse_mode="Markdown",
            )
        else:
            await query.edit_message_text("⚠️ No se pudo actualizar el estado en la base de datos.")
    except Exception as e:
        logger.error(f"Error al procesar callback: {e}")
        await query.edit_message_text(f"⚠️ Error al actualizar apuesta: `{e}`")


# ---------------------------------------------------------------------------
# INICIALIZACIÓN
# ---------------------------------------------------------------------------

def run_bot():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("No se encontró la variable de entorno TELEGRAM_BOT_TOKEN.")

    # Servidor HTTP para Render
    threading.Thread(target=start_health_check_server, daemon=True).start()

    app = Application.builder().token(token).build()

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