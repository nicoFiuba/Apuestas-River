"""
Motor de análisis predictivo cuantitativo para partidos de fútbol.
"""

import logging
from typing import Any
from src.data.api_client import MatchSchema
from src.analytics.poisson import (
    calculate_score_matrix,
    extract_match_probabilities,
    calculate_corner_probabilities,
)
from src.analytics.ev_calculator import BetRecommendationSchema, evaluate_bet
from src.analytics.parlay_builder import SameGameParlaySchema, build_same_game_parlay

logger = logging.getLogger(__name__)


def analyze_single_match(match: MatchSchema) -> dict[str, Any]:
    """
    Ejecuta el análisis estadístico completo de un partido:
    1. Modela intensidades Poisson (goles y córners).
    2. Evalúa valor esperado (+EV) con alcance explícito (Ambos equipos / Local / Visitante).
    3. Construye combinadas Same Game Parlay (SGP).
    """
    try:
        # 1. Estimación de intensidades Lambda según posesión y localía
        is_river_away = "River" in match.away_team
        if is_river_away:
            lambda_home = max(0.8, 1.1 + (match.possession_home - 50) * 0.01)
            lambda_away = max(1.0, 1.5 + (match.possession_away - 50) * 0.01)
        else:
            lambda_home = max(1.2, 1.7 + (match.possession_home - 50) * 0.01)
            lambda_away = max(0.5, 0.9 + (match.possession_away - 50) * 0.01)

        # Matriz de marcadores y probabilidades 1X2 / Over 2.5
        score_matrix = calculate_score_matrix(lambda_home, lambda_away)
        match_probs = extract_match_probabilities(score_matrix)

        # Probabilidades de córners totales
        exp_c_home = float(match.corners_home if match.corners_home > 0 else 4.5)
        exp_c_away = float(match.corners_away if match.corners_away > 0 else 5.5)
        corner_probs = calculate_corner_probabilities(exp_c_home, exp_c_away)

        # 2. Evaluación de Mercados (+EV)
        all_recommendations: list[BetRecommendationSchema] = []

        rec_home = evaluate_bet(
            f"Victoria Local ({match.home_team})",
            float(match_probs["home_win"]),
            float(match.odds.home_win),
        )
        rec_draw = evaluate_bet(
            "Empate (X)",
            float(match_probs["draw"]),
            float(match.odds.draw),
        )
        rec_away = evaluate_bet(
            f"Victoria Visitante ({match.away_team})",
            float(match_probs["away_win"]),
            float(match.odds.away_win),
        )
        all_recommendations.extend([rec_home, rec_draw, rec_away])

        # Mercado Goles Totales (Ambos equipos)
        rec_over = evaluate_bet(
            "Más de 2.5 Goles (Ambos equipos)",
            float(match_probs.get("over_2_5", 0.55)),
            1.92,
        )
        all_recommendations.append(rec_over)

        # Mercado Córners Totales (Ambos equipos)
        p_corners = float(corner_probs.get("over_9_5_corners", corner_probs.get("over_9_5", 0.53)))
        rec_corners = evaluate_bet(
            "Más de 9.5 Córners (Ambos equipos)",
            p_corners,
            1.88,
        )
        all_recommendations.append(rec_corners)

        # Filtrar apuestas con EV+
        ev_plus_bets = [
            bet for bet in all_recommendations
            if getattr(bet, "is_ev_positive", getattr(bet, "expected_value", 0.0) > 0.0)
        ]

        # 3. Construcción del Same Game Parlay (match_id como 1er argumento)
        sgp = build_same_game_parlay(match.match_id, all_recommendations)

        return {
            "match_id": match.match_id,
            "match": match,
            "poisson_probabilities": match_probs,
            "corner_probabilities": corner_probs,
            "all_recommendations": all_recommendations,
            "ev_plus_bets": ev_plus_bets,
            "same_game_parlay": sgp,
        }
    except Exception as e:
        logger.error(f"Error al analizar el partido {match.match_id}: {e}")
        raise