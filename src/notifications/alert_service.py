"""
Servicio de Alertas Automáticas (Telegram Bot API & Notificación Visual).

Envía notificaciones de apuestas con Valor Esperado Positivo (+EV) 
y apuestas combinadas Same Game Parlay a Telegram o consola.
"""

import logging
import httpx

from src.analytics.ev_calculator import BetRecommendationSchema
from src.analytics.parlay_builder import SameGameParlaySchema
from src.utils.config import settings

logger = logging.getLogger(__name__)


def format_alert_message(
    match_teams: str,
    ev_bets: list[BetRecommendationSchema],
    parlay: SameGameParlaySchema | None = None,
) -> str:
    """
    Construye el mensaje formateado de la alerta predictiva con emojis y Markdown.

    Args:
        match_teams (str): Nombre de los equipos (ej. 'River Plate vs Boca Juniors').
        ev_bets (list[BetRecommendationSchema]): Lista de apuestas individuales +EV.
        parlay (SameGameParlaySchema | None): Combinada Same Game Parlay recomendada.

    Returns:
        str: Texto estructurado para Telegram o consola.
    """
    lines: list[str] = []
    lines.append("🚨 *ALERTA DE APUESTA CON VALOR (+EV) DETECTADA* 🚨")
    lines.append(f"⚽ *Partido:* {match_teams}")
    lines.append("────────────────────────────────────────")

    if ev_bets:
        lines.append("🎯 *OPORTUNIDADES DE VALOR INDIVIDUALES:*")
        for bet in ev_bets:
            lines.append(f"• *{bet.market_name}*")
            lines.append(f"  └ Cuota Bet365: `{bet.odds:.2f}` | Prob Real: `{bet.real_prob*100:.1f}%`")
            lines.append(f"  └ *VALOR ESPERADO:* `+{bet.ev_percentage:.1f}%` EV+")
        lines.append("")

    if parlay:
        lines.append(f"🔥 *{parlay.parlay_title.upper()}*")
        lines.append("  └ *Selecciones del Combinado:*")
        for leg in parlay.legs:
            lines.append(f"    - {leg.market_name} (Cuota {leg.odds:.2f})")
        lines.append(f"  💰 *CUOTA TOTAL:* `{parlay.combined_odds:.2f}`")
        lines.append(f"  📊 *EV+ CONJUNTO:* `+{parlay.combined_ev_percentage:.1f}%`")
        lines.append("")

    lines.append("⚠️ *Recomendación:* Operar con gestión de bankroll estricta (Stake 1.5%).")
    return "\n".join(lines)


async def send_telegram_alert(bot_token: str, chat_id: str, message: str) -> bool:
    """
    Envía una petición HTTP POST asíncrona a la API oficial de Telegram Bot.

    Args:
        bot_token (str): Token de autenticación del Bot de Telegram.
        chat_id (str): ID del canal o chat de destino.
        message (str): Mensaje formateado en Markdown.

    Returns:
        bool: True si Telegram aceptó la notificación, False en caso contrario.
    """
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            logger.info("Notificación enviada exitosamente a Telegram (Chat ID: %s).", chat_id)
            return True
    except httpx.HTTPError as exc:
        logger.error("Error al enviar mensaje a Telegram Bot API: %s", exc)
        return False


async def dispatch_alert(
    match_teams: str,
    ev_bets: list[BetRecommendationSchema],
    parlay: SameGameParlaySchema | None = None,
) -> bool:
    """
    Despacha la alerta a Telegram (si existen credenciales) o a la consola de la aplicación.

    Args:
        match_teams (str): Nombre de los equipos.
        ev_bets (list[BetRecommendationSchema]): Apuestas individuales EV+.
        parlay (SameGameParlaySchema | None): Parlay recomendada.

    Returns:
        bool: True si la alerta fue despachada por algún medio.
    """
    if not ev_bets and not parlay:
        return False

    alert_text = format_alert_message(match_teams, ev_bets, parlay)

    # Imprimir siempre la alerta estilizada en la consola
    print("\n" + "=" * 55)
    print(alert_text)
    print("=" * 55 + "\n")

    # Si hay Token de Telegram configurado, enviar vía API
    if settings.telegram_bot_token and settings.telegram_chat_id:
        logger.info("Enviando alerta a Telegram Bot API...")
        return await send_telegram_alert(
            settings.telegram_bot_token, settings.telegram_chat_id, alert_text
        )

    logger.info("Alertas desplegadas en consola (Sin token de Telegram configurado).")
    return True
