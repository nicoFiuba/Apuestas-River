"""
Servicio Escáner de Oportunidades EV+ en Tiempo Real.

Integra la extracción de cuotas de mercado (Bet365), la inferencia cuantitativa 
de Poisson, el filtrado estricto por EV+ (> +3.5%), la persistencia atómica en MySQL
y el despacho automatizado de alertas a Telegram.
"""

import logging
from typing import Any

from src.analytics.ev_calculator import BetRecommendationSchema
from src.analytics.parlay_builder import SameGameParlaySchema
from src.data.api_client import MatchSchema, fetch_river_matches
from src.data.odds_client import fetch_live_market_odds
from src.db.connection import test_connection
from src.db.init_db import init_database
from src.db.repository import save_matches_bulk
from src.notifications.alert_service import dispatch_alert
from src.services.engine_service import analyze_single_match
from src.utils.config import settings

logger = logging.getLogger(__name__)


async def scan_river_value_bets(
    min_ev_threshold: float = 3.5,
    send_alerts: bool = True,
    save_to_db: bool = True,
) -> dict[str, Any]:
    """
    Ejecuta el ciclo de escaneo automatizado en tiempo real.

    Args:
        min_ev_threshold (float): Umbral estricto mínimo de EV% (3.5%).
        send_alerts (bool): Si es True, despacha alertas automáticas vía Telegram / Consola.
        save_to_db (bool): Si es True y la BD está disponible, persiste los encuentros en MySQL.

    Returns:
        dict[str, Any]: Resumen estructurado del escaneo.
    """
    logger.info("Iniciando escaneo de cuotas y valor esperado para partidos de River Plate...")

    # 1. Recuperar Encuentros
    matches = await fetch_river_matches(settings.api_key)
    if not matches:
        logger.warning("No se encontraron partidos de River Plate para analizar.")
        return {"status": "EMPTY", "matches_scanned": 0, "total_ev_bets": 0, "alerts_sent": 0}

    # 2. Persistir en MySQL si la BD está online
    db_saved = 0
    if save_to_db and test_connection():
        init_database()
        db_saved = save_matches_bulk(matches)

    scanned_results: list[dict[str, Any]] = []
    total_ev_bets = 0
    alerts_sent_count = 0

    # 3. Procesar cada partido con las cuotas vivas del mercado
    for match in matches:
        # Obtener cuotas en tiempo real para el partido
        live_odds_list = await fetch_live_market_odds(settings.api_key, match.match_id)

        # Analizar con el motor predictivo cuantitativo
        report = analyze_single_match(match)

        # Filtrar oportunidades con el umbral estricto especificado (> +3.5% EV)
        strict_ev_bets: list[BetRecommendationSchema] = [
            bet for bet in report["evaluated_bets"] if bet.ev_percentage >= min_ev_threshold
        ]

        sgp: SameGameParlaySchema | None = report.get("same_game_parlay")

        total_ev_bets += len(strict_ev_bets)

        # Despachar alerta si existen apuestas de valor o Parlay recomendada
        if send_alerts and (strict_ev_bets or sgp):
            alert_sent = await dispatch_alert(
                match_teams=report["teams"],
                ev_bets=strict_ev_bets,
                parlay=sgp,
            )
            if alert_sent:
                alerts_sent_count += 1

        scanned_results.append(
            {
                "match_id": match.match_id,
                "teams": report["teams"],
                "strict_ev_bets": strict_ev_bets,
                "same_game_parlay": sgp,
            }
        )

    logger.info(
        "Escaneo completado: %d partidos analizados, %d apuestas EV+ detectadas, %d alertas despachadas.",
        len(matches),
        total_ev_bets,
        alerts_sent_count,
    )

    return {
        "status": "SUCCESS",
        "matches_scanned": len(matches),
        "db_persisted": db_saved,
        "total_ev_bets": total_ev_bets,
        "alerts_sent": alerts_sent_count,
        "results": scanned_results,
    }
