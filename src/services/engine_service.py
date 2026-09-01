"""
Motor cuantitativo que evalúa todos los mercados de Crear Apuesta en Bet365.
"""

import logging
from typing import Any
from src.data.api_client import MatchSchema
from src.analytics.poisson import (
    calculate_score_matrix,
    extract_bet365_catalog_probabilities,
)
from src.analytics.ev_calculator import BetRecommendationSchema, evaluate_bet
from src.analytics.parlay_builder import build_same_game_parlay

logger = logging.getLogger(__name__)


def analyze_single_match(match: MatchSchema) -> dict[str, Any]:
    """Evalúa todos los mercados de Crear Apuesta calculando el valor esperado (+EV)."""
    try:
        is_river_home = "River" in match.home_team
        home_name = match.home_team
        away_name = match.away_team

        # Intensidades Lambda basadas en xG real
        if is_river_home:
            lambda_home = (match.river_xg_scored * 1.10 + match.rival_xg_conceded * 0.90) / 2.0
            lambda_away = (match.rival_xg_scored * 0.85 + match.river_xg_conceded * 0.90) / 2.0
        else:
            lambda_home = (match.rival_xg_scored * 1.10 + match.river_xg_conceded * 0.90) / 2.0
            lambda_away = (match.river_xg_scored * 0.90 + match.rival_xg_conceded * 1.10) / 2.0

        score_matrix = calculate_score_matrix(lambda_home, lambda_away)
        probs = extract_bet365_catalog_probabilities(score_matrix, lambda_home, lambda_away)

        all_recommendations: list[BetRecommendationSchema] = []

        # 1. Resultado (1X2)
        all_recommendations.append(evaluate_bet(f"Resultado: {home_name}", probs["home_win"], match.odds.home_win))
        all_recommendations.append(evaluate_bet("Resultado: Empate", probs["draw"], match.odds.draw))
        all_recommendations.append(evaluate_bet(f"Resultado: {away_name}", probs["away_win"], match.odds.away_win))

        # 2. Doble Oportunidad
        all_recommendations.append(evaluate_bet(f"Doble Oportunidad: {home_name} o Empate", probs["home_or_draw"], 1.14 if is_river_home else 1.85))
        all_recommendations.append(evaluate_bet(f"Doble Oportunidad: {away_name} o Empate", probs["away_or_draw"], 2.80 if is_river_home else 1.25))

        # 3. Ambos Equipos Anotarán
        all_recommendations.append(evaluate_bet("Ambos equipos anotarán: Sí", probs["btts_yes"], 2.10))
        all_recommendations.append(evaluate_bet("Ambos equipos anotarán: No", probs["btts_no"], 1.70))

        # 4. Total de Goles
        all_recommendations.append(evaluate_bet("Total de goles: Más de 1.5", probs["over_1_5"], 1.30))
        all_recommendations.append(evaluate_bet("Total de goles: Más de 2.5", probs["over_2_5"], 1.95))
        all_recommendations.append(evaluate_bet("Total de goles: Menos de 2.5", probs["under_2_5"], 1.85))
        all_recommendations.append(evaluate_bet("Total de goles: Menos de 3.5", probs["under_3_5"], 1.32))

        # 5. Rango de Goles
        all_recommendations.append(evaluate_bet("Rango de goles: 2-3 goles", probs["range_2_3"], 2.05))
        all_recommendations.append(evaluate_bet("Rango de goles: 0-1 goles", probs["range_0_1"], 3.50))
        all_recommendations.append(evaluate_bet("Rango de goles: 4+ goles", probs["range_4_plus"], 3.60))

        # 6. Medio tiempo / Resultado final
        all_recommendations.append(evaluate_bet(f"Descanso/Final: Empate / {home_name}", probs["ht_draw_ft_home"], 4.20))
        all_recommendations.append(evaluate_bet(f"Descanso/Final: {home_name} / {home_name}", probs["ht_home_ft_home"], 2.10))

        # 7. Mitad con mayor número de goles
        all_recommendations.append(evaluate_bet("Mitad con más goles: 2ª Mitad", probs["more_goals_2nd_half"], 2.05))

        # 8. Equipo - Goleador (Goles por equipo)
        all_recommendations.append(evaluate_bet(f"Total goles {home_name}: Más de 1.5", probs["home_over_1_5"], 1.58 if is_river_home else 3.20))
        all_recommendations.append(evaluate_bet(f"Total goles {away_name}: Más de 0.5", probs["away_over_0_5"], 1.85 if is_river_home else 1.25))

        # 9. Margen de Victoria
        all_recommendations.append(evaluate_bet(f"Margen de victoria: {home_name} por 1 gol", probs["margin_home_1"], 3.50))
        all_recommendations.append(evaluate_bet(f"Margen de victoria: {home_name} por 2 o más", probs["margin_home_2plus"], 2.25))
        all_recommendations.append(evaluate_bet(f"Margen de victoria: {away_name} por 1 gol", probs["margin_away_1"], 8.50))

        # 10. Equipo - Especiales
        all_recommendations.append(evaluate_bet(f"Especial: {home_name} gana sin recibir goles", probs["home_win_to_nil"], 2.20))
        all_recommendations.append(evaluate_bet(f"Especial: {home_name} anota en ambas mitades", probs["home_scores_both_halves"], 2.40))

        # Construcción del SGP garantizando cuota >= 3.00
        sgp = build_same_game_parlay(match.match_id, all_recommendations, min_odds_floor=3.00)

        return {
            "match_id": match.match_id,
            "match": match,
            "poisson_probabilities": probs,
            "all_recommendations": all_recommendations,
            "same_game_parlay": sgp,
        }
    except Exception as e:
        logger.error(f"Error al analizar partido {match.match_id}: {e}")
        raise