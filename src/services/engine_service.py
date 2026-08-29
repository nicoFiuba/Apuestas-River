"""
Motor de análisis predictivo cuantitativo para partidos de fútbol.
"""

import logging
from typing import Any
from src.data.api_client import MatchSchema
from src.analytics.poisson import (
    estimate_match_lambdas,
    calculate_match_probabilities,
    calculate_corner_probabilities,
)
from src.analytics.ev_calculator import BetRecommendationSchema, evaluate_bet
from src.analytics.parlay_builder import SameGameParlaySchema, build_same_game_parlay

logger = logging.getLogger(__name__)


def analyze_single_match(match: MatchSchema) -> dict[str, Any]:
    """
    Ejecuta el análisis estadístico completo de un partido:
    1. Modela intensidades Poisson (goles y córners).
    2. Evalúa valor esperado (+EV) en mercados 1X2, goles y córners con alcance explícito.
    3. Construye combinadas Same Game Parlay (SGP) optimizadas con criterio de Kelly.
    """
    try:
        # 1. Cálculo de probabilidades Poisson
        lambda_home, lambda_away = estimate_match_lambdas(match)
        match_probs = calculate_match_probabilities(lambda_home, lambda_away)
        corner_probs = calculate_corner_probabilities(match.corners_home, match.corners_away)

        # 2. Evaluación de Mercados Individuales (+EV) con detalle de alcance
        all_recommendations: list[BetRecommendationSchema] = []

        # Mercado 1X2 (Especificando local / visitante explícito)
        rec_home = evaluate_bet(
            f"Victoria Local ({match.home_team})",
            match_probs["home_win"],
            match.odds.home_win,
        )
        rec_draw = evaluate_bet(
            "Empate (X)",
            match_probs["draw"],
            match.odds.draw,
        )
        rec_away = evaluate_bet(
            f"Victoria Visitante ({match.away_team})",
            match_probs["away_win"],
            match.odds.away_win,
        )
        all_recommendations.extend([rec_home, rec_draw, rec_away])

        # Mercado Goles (Ambos equipos combinados)
        rec_over = evaluate_bet(
            "Más de 2.5 Goles (Ambos equipos)",
            match_probs["over_2_5"],
            1.92,
        )
        all_recommendations.append(rec_over)

        # Mercado Córners (Ambos equipos combinados)
        corners_over_p = corner_probs.get("over_9_5_corners", 0.52)
        rec_corners = evaluate_bet(
            "Más de 9.5 Córners (Ambos equipos)",
            corners_over_p,
            1.88,
        )
        all_recommendations.append(rec_corners)

        # Filtrar apuestas individuales con Valor Esperado Positivo (+EV)
        ev_plus_bets = [
            bet for bet in all_recommendations
            if getattr(bet, "is_ev_positive", getattr(bet, "expected_value", 0.0) > 0.0)
        ]

        # 3. Construcción del Same Game Parlay (SGP)
        sgp = build_same_game_parlay(all_recommendations, match)

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