import os
import asyncio
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from src.data.odds_client import fetch_real_soccer_odds
from src.analysis.stats import get_team_poisson_ratings
from src.analysis.poisson import (
    calculate_poisson_lambdas,
    generate_score_matrix,
    evaluate_market_combination,
    CONDITIONS
)
from src.analysis.kelly import calculate_kelly_stake
from src.db.tracker import record_bet, resolve_bet, get_performance_summary, save_odds_history

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=BASE_DIR / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

USER_BANKROLL = float(os.getenv("USER_BANKROLL", "10000.0"))
ARGENTINA_LOTBA_BOOKMAKERS = ["Betsson", "Codere", "Betano", "Sportsbet", "Coolbet", "1xBet", "Bovada", "Pinnacle"]
MIN_TARGET_ODDS = 3.00


# --- MINI SERVIDOR HTTP PARA PLAN GRATUITO EN RENDER ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot cuantitativo de River Plate OK")

    def log_message(self, format, *args):
        return  # Desactivar logs ruidosos del servidor HTTP


def start_dummy_server():
    port = int(os.getenv("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    logging.info(f"🌐 Servidor Web de salud iniciado en puerto {port}")
    server.serve_forever()


def calculate_ev(real_prob: float, odds: float) -> float:
    return (real_prob * odds) - 1.0


def build_combinations_catalog() -> list[dict]:
    return [
        {
            "name": "River Gana sin recibir goles (A Valla Invicta)",
            "conds": [CONDITIONS["RIVER_WIN_CLEAN"]],
            "base_odds_mult": 1.65
        },
        {
            "name": "River Gana + Más de 2.5 Goles Totales",
            "conds": [CONDITIONS["RIVER_WIN"], CONDITIONS["OVER_25"]],
            "base_odds_mult": 1.55
        },
        {
            "name": "River Gana + Ambos Anotan (BTTS Sí)",
            "conds": [CONDITIONS["RIVER_WIN"], CONDITIONS["BTTS_YES"]],
            "base_odds_mult": 1.90
        },
        {
            "name": "River Marca Más de 2.5 Goles Individuales",
            "conds": [CONDITIONS["RIVER_OVER_25"]],
            "base_odds_mult": 1.75
        },
        {
            "name": "River Gana + River +1.5 Goles + Ambos Anotan",
            "conds": [CONDITIONS["RIVER_WIN"], CONDITIONS["RIVER_OVER_15"], CONDITIONS["BTTS_YES"]],
            "base_odds_mult": 2.20
        },
        {
            "name": "River Gana + Más de 3.5 Goles Totales",
            "conds": [CONDITIONS["RIVER_WIN"], CONDITIONS["OVER_35"]],
            "base_odds_mult": 2.40
        },
        {
            "name": "River Gana Ambas Mitades / Dominio (+2.5 Goles y Valla Invicta)",
            "conds": [CONDITIONS["RIVER_WIN_CLEAN"], CONDITIONS["RIVER_OVER_25"]],
            "base_odds_mult": 2.60
        }
    ]


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "⚽ *BOT DE ANÁLISIS DE VARIANTES RIVER PLATE (CUOTAS x3+)* ⚽\n\n"
        "Comandos disponibles:\n"
        "• `/cuotas` - Analizar mercados distintos y sugerir la mejor opción (≥ 3.00)\n"
        "• `/balance` - Ver historial y ganancias en la Base de Datos\n"
        "• `/registrar <casa> <cuota> <monto>` - Registrar apuesta efectuada\n"
        "• `/resolver <id_apuesta> <WIN/LOSS>` - Cerrar apuesta terminada"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")


async def analyze_river_matches():
    matches = await fetch_real_soccer_odds()
    river_matches = [m for m in matches if "River" in m.home_team or "River" in m.away_team]

    if not river_matches:
        return None, [], "❌ No se encontraron partidos próximos de River Plate."

    reports = []
    movement_alerts = []
    combo_catalog = build_combinations_catalog()

    for match in river_matches:
        is_home = "River" in match.home_team
        match_title = f"{match.home_team} vs {match.away_team}"
        
        ratings = get_team_poisson_ratings(match.home_team, match.away_team)
        lambda_river, lambda_rival = calculate_poisson_lambdas(
            ratings["home_attack"], ratings["home_defense"],
            ratings["away_attack"], ratings["away_defense"],
            is_river_home=is_home
        )

        matrix = generate_score_matrix(lambda_river, lambda_rival)
        unique_market_bets = []

        for item in combo_catalog:
            prob_joint = evaluate_market_combination(matrix, item["conds"])
            best_offer_for_market = None

            for bm in match.bookmakers:
                if not any(lotba_bm.lower() in bm.bookmaker.lower() for lotba_bm in ARGENTINA_LOTBA_BOOKMAKERS):
                    continue

                odds_river_1x2 = bm.home_win if is_home else bm.away_win
                
                odds_movement = save_odds_history(match_title, bm.bookmaker, odds_river_1x2)
                if odds_movement:
                    movement_alerts.append(f"⚽ *{match_title}* en *{bm.bookmaker}*:\n{odds_movement}")

                implied_odds = round(odds_river_1x2 * item["base_odds_mult"], 2)

                if implied_odds >= MIN_TARGET_ODDS:
                    ev = calculate_ev(prob_joint, implied_odds)
                    if ev > 0.05:
                        kelly_res = calculate_kelly_stake(
                            bankroll=USER_BANKROLL,
                            odds=implied_odds,
                            real_prob=prob_joint,
                            fraction=0.25,
                            min_stake=15.0
                        )
                        candidate = {
                            "bookmaker": bm.bookmaker,
                            "bet_name": item["name"],
                            "odds": implied_odds,
                            "prob": prob_joint,
                            "ev": ev,
                            "stake": kelly_res["stake_ars"],
                            "bank_pct": kelly_res["bank_percentage"]
                        }
                        if best_offer_for_market is None or candidate["ev"] > best_offer_for_market["ev"]:
                            best_offer_for_market = candidate

            if best_offer_for_market:
                unique_market_bets.append(best_offer_for_market)

        unique_market_bets.sort(key=lambda x: x["ev"], reverse=True)

        if unique_market_bets:
            best_bet = unique_market_bets[0]
            
            alternatives_text = ""
            if len(unique_market_bets) > 1:
                alt_lines = []
                for alt in unique_market_bets[1:]:
                    alt_lines.append(
                        f"• *{alt['bet_name']}* ({alt['bookmaker']})\n"
                        f"   Cuota `{alt['odds']:.2f}` | Prob: `{alt['prob']*100:.1f}%` | EV+: `+{(alt['ev']*100):.1f}%`\n"
                        f"   💰 Stake: `${alt['stake']:.0f} ARS`"
                    )
                alternatives_text = "\n\n📌 *OTRAS OPCIONES DE MERCADOS DISTINTOS (≥ 3.00):*\n" + "\n\n".join(alt_lines)

            report = (
                f"📊 *ANÁLISIS DE MERCADOS Y RECOMENDACIÓN* 📊\n\n"
                f"⚽ *Partido:* {match.home_team} vs {match.away_team}\n"
                f"📅 *Fecha:* `{match.commence_time}`\n"
                f"🎯 *xG Esperados River:* `{lambda_river}` goles | Rival: `{lambda_rival}` goles\n\n"
                f"🏆 *OPCIÓN PRINCIPAL (MÁXIMO EV+ CON CUOTA ≥ 3.00):*\n"
                f"🎯 *Mercado:* *{best_bet['bet_name']}*\n"
                f"🏢 *Mejor Casa:* {best_bet['bookmaker']}\n"
                f"📈 *Cuota Final:* `{best_bet['odds']:.2f}`\n"
                f"🎲 *Probabilidad Conjunta Real:* `{best_bet['prob']*100:.1f}%`\n"
                f"💎 *Valor Esperado (EV+):* `+{(best_bet['ev']*100):.1f}%`\n"
                f"💰 *Stake Sugerido (Kelly 1/4):* `${best_bet['stake']:.0f} ARS` ({best_bet['bank_pct']}% bank)\n"
                f"{alternatives_text}\n\n"
                f"💡 _Armá la opción elegida usando el Creador de Apuestas / Bet Builder._"
            )
            reports.append(report)

    return reports, movement_alerts, None


async def cuotas_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔎 Evaluando mercados distintos (x3+) para River...")
    reports, movements, error = await analyze_river_matches()

    if error:
        await update.message.reply_text(error)
        return

    if movements:
        move_text = "🚨 *ALERTAS DE MOVIMIENTO DE CUOTAS (DROPPING/RISING)* 🚨\n\n" + "\n\n".join(movements)
        await update.message.reply_text(move_text, parse_mode="Markdown")

    if reports:
        for rep in reports:
            await update.message.reply_text(rep, parse_mode="Markdown")
    else:
        await update.message.reply_text("No se encontraron variantes con cuota ≥ 3.00 que cumplan con un EV+ aceptable.")


async def background_monitoring_job(context: ContextTypes.DEFAULT_TYPE):
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not chat_id:
        return

    try:
        logging.info("🔄 Monitoreo en segundo plano ejecutado...")
        reports, movements, _ = await analyze_river_matches()
        if movements:
            move_text = "🚨 *MOVIMIENTO DE CUOTA DETECTADO EN RIVER PLATE* 🚨\n\n" + "\n\n".join(movements)
            await context.bot.send_message(chat_id=chat_id, text=move_text, parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Error en tarea de monitoreo: {e}")


async def registrar_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        args = context.args
        if len(args) < 3:
            await update.message.reply_text("⚠️ Uso correcto: `/registrar <casa> <cuota> <monto>`\nEjemplo: `/registrar Bet365 3.40 1500`", parse_mode="Markdown")
            return

        bookmaker = args[0]
        odds = float(args[1])
        stake = float(args[2])

        bet_id = record_bet(
            match_name="River Plate vs Opponent",
            selection="Variante Recomendada x3+",
            bookmaker=bookmaker,
            odds=odds,
            ev_percentage=25.0,
            stake_ars=stake
        )

        await update.message.reply_text(
            f"✅ *APUESTA REGISTRADA EN BASE DE DATOS*\n\n"
            f"• *ID Apuesta:* `{bet_id}`\n"
            f"• *Casa:* {bookmaker}\n"
            f"• *Cuota:* `{odds:.2f}`\n"
            f"• *Monto Apostado:* `${stake:.2f} ARS`\n"
            f"• *Estado:* `PENDIENTE`\n\n"
            f"💡 Para cerrarla cuando termine usá:\n`/resolver {bet_id} WIN` o `/resolver {bet_id} LOSS`",
            parse_mode="Markdown"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Error al registrar apuesta: {e}")


async def resolver_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        args = context.args
        if len(args) < 2:
            await update.message.reply_text("⚠️ Uso correcto: `/resolver <id_apuesta> <WIN/LOSS>`\nEjemplo: `/resolver 1 WIN`", parse_mode="Markdown")
            return

        bet_id = int(args[0])
        status = args[1].upper()

        if status not in ["WIN", "LOSS", "VOID"]:
            await update.message.reply_text("⚠️ El resultado debe ser `WIN`, `LOSS` o `VOID`.")
            return

        success = resolve_bet(bet_id, status)
        if success:
            await update.message.reply_text(f"🎉 *APUESTA #{bet_id} RESUELTA COMO [{status}] EN LA BASE DE DATOS*", parse_mode="Markdown")
        else:
            await update.message.reply_text(f"❌ No se encontró la apuesta con ID #{bet_id}.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error al resolver apuesta: {e}")


async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats = get_performance_summary()
    text = (
        f"📊 *RESUMEN DE RENDIMIENTO DE APUESTAS*\n\n"
        f"• *Apuestas Totales Finalizadas:* `{stats['total_bets']}`\n"
        f"• *Efectividad (Win Rate):* `{stats['win_rate']}%`\n"
        f"• *Total Invertido:* `${stats['total_staked']:,.2f} ARS`\n"
        f"• *Ganancia Neta (Profit):* `${stats['total_profit']:,.2f} ARS`\n"
        f"• *Rendimiento (Yield):* `{stats['yield_percentage']}%`"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        logging.error("TELEGRAM_BOT_TOKEN no configurado en el archivo .env")
        return

    # Iniciar mini servidor web en segundo plano
    threading.Thread(target=start_dummy_server, daemon=True).start()

    app = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("cuotas", cuotas_command))
    app.add_handler(CommandHandler("registrar", registrar_command))
    app.add_handler(CommandHandler("resolver", resolver_command))
    app.add_handler(CommandHandler("balance", balance_command))

    if app.job_queue:
        app.job_queue.run_repeating(background_monitoring_job, interval=1800, first=10)

    logging.info("🤖 BOT ANALIZADOR DE RIVER PLATE (CON SERVIDOR DE SALUD PARA RENDER) INICIADO.")
    app.run_polling()


if __name__ == "__main__":
    main()
