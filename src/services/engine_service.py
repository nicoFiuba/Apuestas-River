"""
Motor de análisis predictivo cuantitativo con intensidades Poisson calculadas
a partir de métricas xG reales de los equipos.
"""

import logging
from typing import Any
from src.data.api_client import MatchSchema
from src.analytics.poisson import (
    calculate_score_matrix,
    extract_match_probabilities,
    calculate_corner_probabilities,
    calculate_discipline_and_fouls_probabilities,
)
from src.analytics.ev_calculator import BetRecommendationSchema, evaluate_bet
from src.analytics.parlay_builder import build_same_game_parlay

logger = logging.getLogger(__name__)


def analyze_single_match(match: MatchSchema) -> dict[str, Any]:
    """
    Calcula intensidades Poisson empíricas basadas en xG real,
    posesión y córners para encontrar valor (+EV) con cuota >= 3.00.
    """
    try:
        is_river_home = "River" in match.home_team
        river_name = match.home_team if is_river_home else match.away_team

        # 1. Cálculo de Lambdas (Goles esperados) con xG real ponderado por localía
        if is_river_home:
            lambda_home = (match.river_xg_scored * 1.10 + match.rival_xg_conceded * 0.90) / 2.0
            lambda_away = (match.rival_xg_scored * 0.85 + match.river_xg_conceded * 0.90) / 2.0
        else:
            lambda_home = (match.rival_xg_scored * 1.10 + match.river_xg_conceded * 0.90) / 2.0
            lambda_away = (match.river_xg_scored * 0.90 + match.rival_xg_conceded * 1.10) / 2.0

        # Generar matriz de marcadores Poisson
        score_matrix = calculate_score_matrix(lambda_home, lambda_away)
        probs = extract_match_probabilities(score_matrix, is_river_away=(not is_river_home))

        # Córners y disciplina
        corner_probs = calculate_corner_probabilities(match.corners_home, match.corners_away)
        disc_probs = calculate_discipline_and_fouls_probabilities(
            expected_cards=match.cards_expected,
            expected_fouls=match.fouls_expected,
        )

        all_recommendations: list[BetRecommendationSchema] = []

        # 1. Resultado 1X2
        all_recommendations.append(evaluate_bet(f"Resultado: {match.home_team}", probs["home_win"], match.odds.home_win))
        all_recommendations.append(evaluate_bet("Resultado: Empate", probs["draw"], match.odds.draw))
        all_recommendations.append(evaluate_bet(f"Resultado: {match.away_team}", probs["away_win"], match.odds.away_win))

        # 2. Doble Oportunidad
        if is_river_home:
            all_recommendations.append(evaluate_bet(f"Doble Oportunidad: {river_name} o Empate", probs["home_or_draw"], 1.14))
        else:
            all_recommendations.append(evaluate_bet(f"Doble Oportunidad: {river_name} o Empate", probs["away_or_draw"], 1.30))

        # 3. Goles Totales
        all_recommendations.append(evaluate_bet("Total de goles: Más de 1.5", probs["over_1_5"], 1.32))
        all_recommendations.append(evaluate_bet("Total de goles: Más de 2.5", probs["over_2_5"], 1.95))
        all_recommendations.append(evaluate_bet("Total de goles: Más de 3.5", probs["over_3_5"], 3.40))

        # 4. Ambos Equipos Anotarán
        all_recommendations.append(evaluate_bet("Ambos equipos anotarán: Sí", probs["btts_yes"], 2.10))
        all_recommendations.append(evaluate_bet("Ambos equipos anotarán: No", probs["btts_no"], 1.70))

        # 5. Goles de River Plate
        all_recommendations.append(evaluate_bet(f"Total de goles de {river_name}: Más de 1.5", probs["river_over_1_5"], 1.62))

        # 6. Córners
        all_recommendations.append(evaluate_bet("Total de córners: Más de 8.5", corner_probs["over_8_5_corners"], 1.50))
        all_recommendations.append(evaluate_bet("Total de córners: Más de 9.5", corner_probs["over_9_5_corners"], 1.85))

        # 7. Tarjetas y Faltas
        all_recommendations.append(evaluate_bet("Total de tarjetas: Más de 4.5", disc_probs["over_4_5_cards"], 1.80))
        all_recommendations.append(evaluate_bet("Total de faltas: Más de 24.5", disc_probs["over_23_5_fouls"], 1.75))

        # 8. Margen de Victoria
        all_recommendations.append(evaluate_bet(f"Margen de victoria: {river_name} por 2 o más", probs["margin_river_2plus"], 2.25))

        # Construcción del ticket (Simple o SGP con cuota >= 3.00)
        sgp = build_same_game_parlay(match.match_id, all_recommendations, min_odds_floor=3.00)

        return {
            "match_id": match.match_id,
            "match": match,
            "poisson_probabilities": probs,
            "corner_probabilities": corner_probs,
            "discipline_probabilities": disc_probs,
            "all_recommendations": all_recommendations,
            "same_game_parlay": sgp,
        }
    except Exception as e:
        logger.error(f"Error al analizar partido {match.match_id}: {e}")
        raise