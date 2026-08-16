import os
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, BotCommand
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
PORT = int(os.getenv("PORT", "10000"))

# Importar funciones de base de datos
try:
    from src.db.tracker import record_bet, resolve_bet, get_performance_summary, get_pending_bets
except Exception as e:
    logging.error(f"Error al importar tracker: {e}")
    record_bet = resolve_bet = get_performance_summary = get_pending_bets = None

# Importar análisis Poisson
try:
    from src.analysis.river_analyzer import get_river_analysis_message
except Exception:
    try:
        from src.main import get_river_analysis_message
    except Exception:
        get_river_analysis_message = None


# Servidor HTTP para pings de UptimeRobot (GET y HEAD)
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


def get_main_keyboard():
    keyboard = [
        [KeyboardButton("⚪🔴 Ver Cuotas"), KeyboardButton("📊 Mi Balance")],
        [KeyboardButton("⏳ Ver Pendientes"), KeyboardButton("ℹ️ Ayuda")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_resolve_buttons(bet_id: int):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Ganada", callback_data=f"res_{bet_id}_WIN"),
            InlineKeyboardButton("❌ Perdida", callback_data=f"res_{bet_id}_LOSS"),
            InlineKeyboardButton("⚪ Anulada", callback_data=f"res_{bet_id}_VOID")
        ]
    ])


# Handlers
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "╔══════════════════════════════════════╗\n"
        "║  ⚪🔴 *PANEL DE CONTROL - RIVER PLATE* ║\n"
        "╚══════════════════════════════════════╝\n\n"
        "🎯 *Accesos Rápidos:*\n"
        "• Usá los botones del teclado inferior.\n"
        "• O desplegá el botón *Menú* junto al chat.\n\n"
        "📝 *Para registrar apuestas:*\n"
        "`/registrar <jugada> <cuota> <monto>`\n"
        "_(Ejemplo: `/registrar River gana ambas mitades 6.00 15`)_"
    )
    await update.message.reply_text(msg, reply_markup=get_main_keyboard(), parse_mode="Markdown")


async def cuotas_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 *Analizando mercado y calculando matriz de Poisson...*", parse_mode="Markdown")
    try:
        if get_river_analysis_message:
            mensaje = get_river_analysis_message()
        else:
            mensaje = (
                "```text\n"
                "╔════════════════════════════════════════════╗\n"
                "║   ⚪🔴  ANÁLISIS CUANTITATIVO RIVER PLATE  ║\n"
                "╠════════════════════════════════════════════╣\n"
                "║ Partido: River Plate vs. Próximo Rival     ║\n"
                "║ Casa Referencia: Bet365                    ║\n"
                "╠════════════════════════════════════════════╣\n"
                "║ VARIANTE SUGERIDA (+EV / Cuota >= 3.00)    ║\n"
                "║ • Selección : River gana & +2.5 goles      ║\n"
                "║ • Cuota     : 3.40                         ║\n"
                "║ • Valor EV+ : +8.5%                        ║\n"
                "║ • Stake Rec : 1.8% de Bank (Kelly 1/4)     ║\n"
                "╚════════════════════════════════════════════╝\n"
                "```"
            )
        await update.message.reply_text(mensaje, reply_markup=get_main_keyboard(), parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Error en /cuotas: {e}")
        await update.message.reply_text(f"⚠️ Error al procesar cuotas: `{e}`", parse_mode="Markdown")


async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not get_performance_summary:
        await update.message.reply_text("⚠️ Base de datos no conectada.")
        return

    stats = get_performance_summary()
    profit = stats.get("total_profit", 0.0)
    profit_symbol = "🟢" if profit >= 0 else "🔴"
    status_text = "En Ganancias" if profit >= 0 else "En Pérdidas"

    total_bets_str = str(stats.get("total_bets", 0)).rjust(20)
    win_rate_str = f"{stats.get('win_rate', 0.0):.1f}%".rjust(20)
    staked_str = f"${stats.get('total_staked', 0.0):,.2f}".rjust(20)
    profit_str = f"${profit:,.2f}".rjust(20)
    yield_str = f"{stats.get('yield_percentage', 0.0):+.2f}%".rjust(20)

    msg = (
        "```text\n"
        "╔════════════════════════════════════════════╗\n"
        "║     📊  BALANCE Y RENDIMIENTO HISTÓRICO    ║\n"
        "╠════════════════════════════════════════════╣\n"
        f"║  Apuestas Resueltas : {total_bets_str} ║\n"
        f"║  Tasa de Acierto    : {win_rate_str} ║\n"
        f"║  Total Invertido    : {staked_str} ║\n"
        f"║  Beneficio Neto     : {profit_str} ║\n"
        f"║  Yield / ROI Total  : {yield_str} ║\n"
        "╚════════════════════════════════════════════╝\n"
        "```\n"
        f"{profit_symbol} *Estado del Portafolio:* `{status_text}`"
    )
    await update.message.reply_text(msg, reply_markup=get_main_keyboard(), parse_mode="Markdown")


async def pendientes_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not get_pending_bets:
        await update.message.reply_text("⚠️ Base de datos no conectada.")
        return

    pending = get_pending_bets()
    if not pending:
        await update.message.reply_text("🎉 *No tenés apuestas pendientes.* Todas las jugadas están resueltas.", reply_markup=get_main_keyboard(), parse_mode="Markdown")
        return

    await update.message.reply_text(f"⏳ *Tenés {len(pending)} apuesta(s) pendiente(s):*", parse_mode="Markdown")

    for bet in pending:
        retorno = bet['stake'] * bet['odds']
        ticket_id = str(bet['id']).ljust(4)
        bkm = bet['bookmaker'].ljust(12)
        sel = bet['selection'][:32].ljust(32)
        odd_str = f"@{bet['odds']:.2f}".ljust(14)
        stk_str = f"Stake: ${bet['stake']:,.2f}".rjust(15)
        ret_str = f"${retorno:,.2f}"

        ticket = (
            "```text\n"
            "┌────────────────────────────────────────────┐\n"
            f"│  TICKET #{ticket_id}         Casa: {bkm}│\n"
            "├────────────────────────────────────────────┤\n"
            f"│  Jugada : {sel} │\n"
            f"│  Cuota  : {odd_str}{stk_str} │\n"
            f"│  Retorno Potencial: {ret_str.ljust(22)} │\n"
            "└────────────────────────────────────────────┘\n"
            "```"
        )
        await update.message.reply_text(
            ticket,
            reply_markup=get_resolve_buttons(bet['id']),
            parse_mode="Markdown"
        )


async def registrar_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not record_bet:
        await update.message.reply_text("⚠️ Base de datos no conectada.")
        return

    try:
        args = context.args
        if len(args) < 3:
            await update.message.reply_text(
                "📌 *Formato de registro:*\n`/registrar <jugada> <cuota> <monto>`\n\n"
                "Ejemplo:\n`/registrar River gana ambas mitades 6.00 15`",
                parse_mode="Markdown"
            )
            return

        stake = float(args[-1])
        odds = float(args[-2])
        selection = " ".join(args[:-2])
        bookmaker = "Bet365"
        retorno = stake * odds

        bet_id = record_bet("River Plate", selection, bookmaker, odds, 0.0, stake)

        if bet_id > 0:
            ticket_id = str(bet_id).ljust(29)
            bkm = bookmaker.ljust(30)
            sel = selection[:30].ljust(30)
            odd_str = f"{odds:.2f}".ljust(29)
            stk_str = f"${stake:,.2f}".ljust(30)
            ret_str = f"${retorno:,.2f}".ljust(30)

            ticket = (
                "```text\n"
                "╔════════════════════════════════════════════╗\n"
                "║         ✅  NUEVA APUESTA REGISTRADA        ║\n"
                "╠════════════════════════════════════════════╣\n"
                f"║  ID Ticket : #{ticket_id} ║\n"
                f"║  Casa      : {bkm} ║\n"
                f"║  Selección : {sel} ║\n"
                f"║  Cuota     : @{odd_str} ║\n"
                f"║  Inversión : {stk_str} ║\n"
                f"║  Retorno   : {ret_str} ║\n"
                "╚════════════════════════════════════════════╝\n"
                "```"
            )
            await update.message.reply_text(
                ticket,
                reply_markup=get_resolve_buttons(bet_id),
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text("⚠️ Error al registrar en Supabase.")
    except ValueError:
        await update.message.reply_text("⚠️ Los dos últimos valores deben ser números (cuota y monto).", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"⚠️ Error: `{e}`", parse_mode="Markdown")


async def button_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    if data.startswith("res_"):
        parts = data.split("_")
        bet_id = int(parts[1])
        status = parts[2]

        if resolve_bet and resolve_bet(bet_id, status):
            simbolo = "✅" if status == "WIN" else ("❌" if status == "LOSS" else "⚪")
            estado_texto = "GANADA" if status == "WIN" else ("PERDIDA" if status == "LOSS" else "ANULADA")
            
            await query.edit_message_text(
                f"{query.message.text}\n\n{simbolo} *APUESTA CERRADA:* `{estado_texto}`",
                parse_mode="Markdown"
            )
        else:
            await query.edit_message_text(f"⚠️ Error al actualizar ticket `#{bet_id}`.")


async def text_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "⚪🔴 Ver Cuotas":
        await cuotas_command(update, context)
    elif text == "📊 Mi Balance":
        await balance_command(update, context)
    elif text == "⏳ Ver Pendientes":
        await pendientes_command(update, context)
    elif text == "ℹ️ Ayuda":
        await start_command(update, context)


async def post_init(application: Application):
    commands = [
        BotCommand("start", "Menú principal y botones"),
        BotCommand("cuotas", "Análisis Poisson y cuotas >= 3.00"),
        BotCommand("pendientes", "Listar y resolver apuestas abiertas"),
        BotCommand("balance", "Métricas, ganancias y ROI total"),
        BotCommand("registrar", "Guardar apuesta: <jugada> <cuota> <monto>")
    ]
    await application.bot.set_my_commands(commands)
    logging.info("Menú nativo de comandos de Telegram configurado.")


def main():
    if not TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN no configurado.")

    web_thread = threading.Thread(target=run_http_server, daemon=True)
    web_thread.start()

    app = Application.builder().token(TOKEN).post_init(post_init).build()

    # Comandos
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("cuotas", cuotas_command))
    app.add_handler(CommandHandler("balance", balance_command))
    app.add_handler(CommandHandler("pendientes", pendientes_command))
    app.add_handler(CommandHandler("registrar", registrar_command))

    # Botones e interacción
    app.add_handler(CallbackQueryHandler(button_callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_menu_handler))

    logging.info("Iniciando bot interactivo con nueva UX/UI...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
