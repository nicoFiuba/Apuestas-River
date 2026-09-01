"""
Motor cuantitativo que evalúa los 10 mercados completos de Bet365 Crear Apuesta.
"""

import logging
from typing import Any
from src.data.api_client import MatchSchema
from src.data.market_feed import get_live_bet365_feed, Bet365MarketFeed
from src.analytics.poisson import (
    calculate_score_matrix,
    extract_bet365_catalog_probabilities,
)
from src.analytics.ev_calculator import BetRecommendationSchema, evaluate_bet
from src.analytics.parlay_builder import build_same_game_parlay

logger = logging.getLogger(__name__)


def analyze_single_match(match: MatchSchema, live_feed: Bet365MarketFeed | None = None) -> dict[str, Any]:
    """Evalúa los 10 mercados del catálogo calculando Valor Esperado (+EV)."""
    try:
        feed = live_feed or get_live_bet365_feed()
        is_river_home = "River" in match.home_team
        home_name = match.home_team
        away_name = match.away_team

        # Intensidades Lambda basadas en estadísticas xG reales
        if is_river_home:
            lambda_home = (match.river_xg_scored * 1.10 + match.rival_xg_conceded * 0.90) / 2.0
            lambda_away = (match.rival_xg_scored * 0.85 + match.river_xg_conceded * 0.90) / 2.0
        else:
            lambda_home = (match.rival_xg_scored * 1.10 + match.river_xg_conceded * 0.90) / 2.0
            lambda_away = (match.river_xg_scored * 0.90 + match.rival_xg_conceded * 1.10) / 2.0

        score_matrix = calculate_score_matrix(lambda_home, lambda_away)
        probs = extract_bet365_catalog_probabilities(score_matrix, lambda_home, lambda_away)

        all_recommendations: list[BetRecommendationSchema] = []

        # -------------------------------------------------------------
        # 1. RESULTADO (1X2)
        # -------------------------------------------------------------
        all_recommendations.append(evaluate_bet(f"Resultado: {home_name}", probs["home_win"], feed.result_home))
        all_recommendations.append(evaluate_bet("Resultado: Empate", probs["draw"], feed.result_draw))
        all_recommendations.append(evaluate_bet(f"Resultado: {away_name}", probs["away_win"], feed.result_away))

        # -------------------------------------------------------------
        # 2. AMBOS EQUIPOS ANOTARÁN (BTTS)
        # -------------------------------------------------------------
        all_recommendations.append(evaluate_bet("Ambos equipos anotarán: Sí", probs["btts_yes"], feed.btts_yes))
        all_recommendations.append(evaluate_bet("Ambos equipos anotarán: No", probs["btts_no"], feed.btts_no))

        # -------------------------------------------------------------
        # 3. DOBLE OPORTUNIDAD
        # -------------------------------------------------------------
        all_recommendations.append(evaluate_bet(f"Doble Oportunidad: {home_name} o Empate", probs["home_or_draw"], feed.double_chance_1x))
        all_recommendations.append(evaluate_bet(f"Doble Oportunidad: {away_name} o Empate", probs["away_or_draw"], feed.double_chance_x2))
        all_recommendations.append(evaluate_bet(f"Doble Oportunidad: {home_name} o {away_name}", probs["home_or_away"], feed.double_chance_12))

        # -------------------------------------------------------------
        # 4. TOTAL DE GOLES
        # -------------------------------------------------------------
        all_recommendations.append(evaluate_bet("Total de goles: Más de 1 gol", probs["over_1_5"], feed.over_1_goal))
        all_recommendations.append(evaluate_bet("Total de goles: Más de 2 goles", probs["over_2_5"], feed.over_2_goals))
        all_recommendations.append(evaluate_bet("Total de goles: Más de 3 goles", probs["over_3_5"], feed.over_3_goals))
        all_recommendations.append(evaluate_bet("Total de goles: Menos de 2 goles", probs["under_2_5"], feed.under_2_goals))
        all_recommendations.append(evaluate_bet("Total de goles: Menos de 3 goles", probs["under_3_5"], feed.under_3_goals))

        # -------------------------------------------------------------
        # 5. RANGO DE GOLES
        # -------------------------------------------------------------
        p_1_2 = probs["range_0_1"] * 0.85 + probs["range_2_3"] * 0.5
        all_recommendations.append(evaluate_bet("Rango de goles: 1-2 goles", p_1_2, feed.range_1_2))
        all_recommendations.append(evaluate_bet("Rango de goles: 2-3 goles", probs["range_2_3"], feed.range_2_3))
        all_recommendations.append(evaluate_bet("Rango de goles: 1-3 goles", probs["over_1_5"] - probs["over_3_5"], feed.range_1_3))

        # -------------------------------------------------------------
        # 6. MEDIO TIEMPO / RESULTADO FINAL (HT/FT)
        # -------------------------------------------------------------
        all_recommendations.append(evaluate_bet(f"Descanso/Final: {home_name} - {home_name}", probs["ht_home_ft_home"], feed.ht_river_ft_river))
        all_recommendations.append(evaluate_bet(f"Descanso/Final: Empate - {home_name}", probs["ht_draw_ft_home"], feed.ht_draw_ft_river))
        all_recommendations.append(evaluate_bet("Descanso/Final: Empate - Empate", probs["draw"] * 0.48, feed.ht_draw_ft_draw))
        all_recommendations.append(evaluate_bet(f"Descanso/Final: Empate - {away_name}", probs["away_win"] * 0.45, feed.ht_draw_ft_rival))

        # -------------------------------------------------------------
        # 7. MARCADOR EXACTO
        # -------------------------------------------------------------
        all_recommendations.append(evaluate_bet(f"Marcador: {home_name} 1-0", float(score_matrix[1, 0]), feed.score_1_0))
        all_recommendations.append(evaluate_bet(f"Marcador: {home_name} 2-0", float(score_matrix[2, 0]), feed.score_2_0))
        all_recommendations.append(evaluate_bet(f"Marcador: {home_name} 2-1", float(score_matrix[2, 1]), feed.score_2_1))
        all_recommendations.append(evaluate_bet("Marcador: 0-0 Empate", float(score_matrix[0, 0]), feed.score_0_0))
        all_recommendations.append(evaluate_bet("Marcador: 1-1 Empate", float(score_matrix[1, 1]), feed.score_1_1))

        # -------------------------------------------------------------
        # 8. MITAD CON MAYOR NÚMERO DE GOLES
        # -------------------------------------------------------------
        all_recommendations.append(evaluate_bet("Mitad con más goles: 1ª mitad", probs.get("more_goals_1st_half", 0.30), feed.half_1st_more_goals))
        all_recommendations.append(evaluate_bet("Mitad con más goles: 2ª mitad", probs["more_goals_2nd_half"], feed.half_2nd_more_goals))
        all_recommendations.append(evaluate_bet("Mitad con más goles: Empate", 0.18, feed.halves_equal_goals))

        # -------------------------------------------------------------
        # 9. EQUIPO - ESPECIALES
        # -------------------------------------------------------------
        all_recommendations.append(evaluate_bet(f"Especial: {home_name} ganará a cero", probs["home_win_to_nil"], feed.river_to_nil))
        all_recommendations.append(evaluate_bet(f"Especial: {home_name} anotará en ambas mitades", probs["home_scores_both_halves"], feed.river_both_halves_score))
        all_recommendations.append(evaluate_bet(f"Especial: {home_name} ganará ambas mitades", probs["home_win"] * 0.35, feed.river_win_both_halves))
        all_recommendations.append(evaluate_bet(f"Especial: {home_name} ganará cualquier mitad", probs["home_win"] * 0.90, feed.river_win_any_half))
        all_recommendations.append(evaluate_bet(f"Especial: {away_name} ganará a cero", probs["away_win_to_nil"], feed.rival_to_nil))

        # -------------------------------------------------------------
        # 10. MARGEN DE VICTORIA
        # -------------------------------------------------------------
        all_recommendations.append(evaluate_bet(f"Margen de victoria: {home_name} por 1 gol", probs["margin_home_1"], feed.river_margin_1))
        all_recommendations.append(evaluate_bet(f"Margen de victoria: {home_name} por 2 goles", probs["margin_home_2plus"] * 0.65, feed.river_margin_2))
        all_recommendations.append(evaluate_bet(f"Margen de victoria: {home_name} por 2 goles o más", probs["margin_home_2plus"], feed.river_margin_2plus))
        all_recommendations.append(evaluate_bet(f"Margen de victoria: {home_name} por 3 goles o más", probs["margin_home_2plus"] * 0.38, feed.river_margin_3plus))
        all_recommendations.append(evaluate_bet(f"Margen de victoria: {away_name} por 1 gol", probs["margin_away_1"], feed.rival_margin_1))
        all_recommendations.append(evaluate_bet(f"Margen de victoria: {away_name} por 2 goles o más", probs["margin_away_2plus"], feed.rival_margin_2plus))

        # Constructor SGP con los 10 mercados y piso mínimo de cuota >= @3.00
        sgp = build_same_game_parlay(match.match_id, all_recommendations, min_odds_floor=3.00)

        return {
            "match_id": match.match_id,
            "match": match,
            "poisson_probabilities": probs,
            "all_recommendations": all_recommendations,
            "same_game_parlay": sgp,
        }
    except Exception as e:
        logger.error(f"Error en evaluación de los 10 mercados: {e}")
        raise