"""
Servicio Orquestador del Motor Predictivo de Apuestas.

Consume partidos validados (`MatchSchema`), ejecuta la inferencia estadística
mediante Distribución de Poisson, calcula el Valor Esperado (+EV) de mercados 
y construye combinadas Same Game Parlay (cuotas x3.00+).
"""

import logging
from typing import Any

from src.analytics.ev_calculator import BetRecommendationSchema, evaluate_bet
from src.analytics.parlay_builder import SameGameParlaySchema, build_same_game_parlay
from src.analytics.poisson import (
    calculate_corner_probabilities,
    calculate_score_matrix,
    extract_match_probabilities,
)
from src.data.api_client import MatchSchema

logger = logging.getLogger(__name__)


def estimate_match_lambdas(match: MatchSchema) -> tuple[float, float, float, float]:
    """
    Estima los parámetros de intensidad (lambda) de goles y córners según contexto de River Plate.

    Args:
        match (MatchSchema): Partido a analizar.

    Returns:
        tuple[float, float, float, float]: (lambda_home_goals, lambda_away_goals, corners_home, corners_away)
    """
    is_river_home = "River" in match.home_team

    if is_river_home:
        # River Plate jugando en el MÁS Monumental
        lambda_home = 2.10
        lambda_away = 0.85
        corners_home = 6.5
        corners_away = 3.5
    else:
        # River Plate de visitante
        lambda_home = 1.35
        lambda_away = 1.60
        corners_home = 4.5
        corners_away = 5.5

    return lambda_home, lambda_away, corners_home, corners_away


def analyze_single_match(match: MatchSchema) -> dict[str, Any]:
    """
    Ejecuta el análisis predictivo cuantitativo completo para un único partido.

    Args:
        match (MatchSchema): Partido recuperado de la API/Base de datos.

    Returns:
        dict[str, Any]: Reporte estructurado con probabilidades, apuestas EV+ y Parlay SGP.
    """
    logger.info("Procesando análisis cuantitativo para: %s vs %s", match.home_team, match.away_team)

    # 1. Estimación de Lambdas y Generación de Matriz de Poisson
    lh, la, ch, ca = estimate_match_lambdas(match)
    score_matrix = calculate_score_matrix(lh, la, max_goals=10)
    match_probs = extract_match_probabilities(score_matrix)
    corner_probs = calculate_corner_probabilities(ch, ca)

    # 2. Evaluación de Mercados Individuales (+EV)
    all_recommendations: list[BetRecommendationSchema] = []

    # Mercado 1X2
    rec_home = evaluate_bet(f"Victoria Local ({match.home_team})", match_probs["home_win"], match.odds.home_win)
    rec_draw = evaluate_bet("Empate (X)", match_probs["draw"], match.odds.draw)
    rec_away = evaluate_bet(f"Victoria Visitante ({match.away_team})", match_probs["away_win"], match.odds.away_win)
    all_recommendations.extend([rec_home, rec_draw, rec_away])

    # Mercado Goles Over 2.5 (Cuota estimada ~ 1.90 en mercado)
    rec_over = evaluate_bet("Más de 2.5 Goles", match_probs["over_2_5"], 1.92)
    all_recommendations.append(rec_over)

    # Mercado Córners Over 9.5 (Cuota estimada ~ 1.85 en mercado)
    rec_corners = evaluate_bet("Más de 9.5 Córners Totales", corner_probs["over_9_5_corners"], 1.88)
    all_recommendations.append(rec_corners)

    # Filtrar solo recomendaciones con EV+ real positivo
    ev_plus_recommendations = [r for r in all_recommendations if r.is_recommended]

    # 3. Generación de Same Game Parlay (cuota objetivo >= 3.00)
    sgp: SameGameParlaySchema | None = None
    if len(all_recommendations) >= 2:
        sgp = build_same_game_parlay(
            match_id=match.match_id,
            recommendations=all_recommendations,
            target_min_odds=3.00,
        )

    return {
        "match_id": match.match_id,
        "competition": match.competition,
        "teams": f"{match.home_team} vs {match.away_team}",
        "datetime_utc": match.datetime_utc,
        "stadium": match.stadium,
        "lambdas": {"home_goals": lh, "away_goals": la, "home_corners": ch, "away_corners": ca},
        "poisson_probabilities": match_probs,
        "corner_probabilities": corner_probs,
        "evaluated_bets": all_recommendations,
        "ev_plus_bets": ev_plus_recommendations,
        "same_game_parlay": sgp,
    }


def run_predictive_analysis(matches: list[MatchSchema]) -> list[dict[str, Any]]:
    """
    Orquesta la ejecución del motor predictivo cuantitativo para un lote de partidos.

    Args:
        matches (list[MatchSchema]): Lista de partidos validados.

    Returns:
        list[dict[str, Any]]: Lista de informes analíticos completos.
    """
    if not matches:
        return []

    results: list[dict[str, Any]] = []
    for match in matches:
        report = analyze_single_match(match)
        results.append(report)

    logger.info("Análisis cuantitativo de Poisson y EV+ finalizado para %d partidos.", len(results))
    return results
