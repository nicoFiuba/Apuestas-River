import asyncio
import logging
import os
from src.data.odds_client import fetch_real_soccer_odds
from src.notifications.telegram import send_telegram_alert
from src.analysis.kelly import calculate_kelly_stake

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Configuración inicial de Bankroll (ARS) y Casas Autorizadas
USER_BANKROLL = float(os.getenv("USER_BANKROLL", "10000.0"))

ARGENTINA_LOTBA_BOOKMAKERS = [
    "Betsson",
    "Codere",
    "Betano",
    "Sportsbet",
    "Coolbet",
    "1xBet",
    "Bovada",
    "Pinnacle"
]

last_notified_odds: dict[str, float] = {}


def calculate_ev(real_prob: float, odds: float) -> float:
    return (real_prob * odds) - 1.0


async def check_river_odds_and_notify():
    global last_notified_odds
    logging.info("🔎 Escaneando cuotas en vivo (con gestión de Bankroll y Kelly)...")
    matches = await fetch_real_soccer_odds()

    river_matches = [
        m for m in matches 
        if "River" in m.home_team or "River" in m.away_team
    ]

    if not river_matches:
        logging.warning("No se encontraron partidos próximos de River Plate.")
        return

    for match in river_matches:
        is_home = "River" in match.home_team
        prob_river_win = 0.52 if is_home else 0.44
        prob_draw = 0.28

        new_alert_messages = []

        print("\n" + "="*60)
        print(f"⚽ PARTIDO: {match.home_team} vs {match.away_team}")
        print("="*60)

        for bm in match.bookmakers:
            if not any(lotba_bm.lower() in bm.bookmaker.lower() for lotba_bm in ARGENTINA_LOTBA_BOOKMAKERS):
                continue

            odds_river = bm.home_win if is_home else bm.away_win
            odds_draw = bm.draw

            ev_river = calculate_ev(real_prob=prob_river_win, odds=odds_river)
            ev_draw = calculate_ev(real_prob=prob_draw, odds=odds_draw)

            # 1. Alerta para Ganador River Plate con Stake de Kelly
            if ev_river > 0.15:
                key = f"{match.match_id}_{bm.bookmaker}_river_win"
                prev_odds = last_notified_odds.get(key, 0.0)

                if odds_river != prev_odds:
                    last_notified_odds[key] = odds_river
                    kelly_res = calculate_kelly_stake(
                        bankroll=USER_BANKROLL,
                        odds=odds_river,
                        real_prob=prob_river_win,
                        fraction=0.25,
                        min_stake=15.0
                    )
                    
                    ref_note = " <i>(Usar de ref. para Bet365)</i>" if "Betsson" in bm.bookmaker else ""
                    stake_info = f" 💰 <b>Stake Sugerido:</b> `${kelly_res['stake_ars']:.0f} ARS` ({kelly_res['bank_percentage']}% bank)"
                    
                    new_alert_messages.append(
                        f"• *{bm.bookmaker}* ➔ *Gana River Plate*\n"
                        f"   Cuota `{odds_river:.2f}` | EV+: `+{(ev_river*100):.1f}%`{ref_note}\n"
                        f"  {stake_info}"
                    )

            # 2. Alerta para Empate
            if ev_draw > 0.15 and odds_draw >= 3.00:
                key = f"{match.match_id}_{bm.bookmaker}_draw"
                prev_odds = last_notified_odds.get(key, 0.0)

                if odds_draw != prev_odds:
                    last_notified_odds[key] = odds_draw
                    kelly_res = calculate_kelly_stake(
                        bankroll=USER_BANKROLL,
                        odds=odds_draw,
                        real_prob=prob_draw,
                        fraction=0.25,
                        min_stake=15.0
                    )
                    
                    stake_info = f" 💰 <b>Stake Sugerido:</b> `${kelly_res['stake_ars']:.0f} ARS` ({kelly_res['bank_percentage']}% bank)"
                    new_alert_messages.append(
                        f"• *{bm.bookmaker}* ➔ *Empate (X)*\n"
                        f"   Cuota `{odds_draw:.2f}` | EV+: `+{(ev_draw*100):.1f}%`\n"
                        f"  {stake_info}"
                    )

        if new_alert_messages:
            full_alert = (
                f"🏛️ *SELECCIÓN DE APUESTA CON KELLY STAKE* 🏛️\n\n"
                f"⚽ *Partido:* {match.home_team} vs {match.away_team}\n"
                f"📅 *Fecha:* `{match.commence_time}`\n"
                f"💼 *Bankroll Base:* `${USER_BANKROLL:,.0f} ARS`\n\n"
                f"🎯 *Recomendaciones:* \n\n" +
                "\n\n".join(new_alert_messages) +
                f"\n\n💡 _Tip: Si en Bet365 recién empezás, podés usar el mínimo de $15 ARS en lugar del stake sugerido._"
            )
            logging.info(f"📢 Oportunidades encontradas. Enviando Telegram...")
            await send_telegram_alert(full_alert)
        else:
            logging.info("No se encontraron cuotas EV+ para las casas seleccionadas.")


async def start_continuous_monitoring(interval_minutes: int = 180):
    logging.info(f"🚀 MONITOR CON GESTIÓN DE KELLY STAKE (Intervalo: {interval_minutes} min)")
    while True:
        try:
            await check_river_odds_and_notify()
        except Exception as e:
            logging.error(f"Error durante la ejecución del escáner: {e}")
        
        logging.info(f"Próxima verificación en {interval_minutes} minutos... (Presioná Ctrl+C para detener)")
        await asyncio.sleep(interval_minutes * 60)


if __name__ == "__main__":
    asyncio.run(start_continuous_monitoring(interval_minutes=180))
