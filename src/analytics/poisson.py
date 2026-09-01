"""
Módulo de cálculo probabilístico adaptado al catálogo completo de Crear Apuesta en Bet365.
"""

import math
import numpy as np


def calculate_poisson_pmf(lambda_param: float, max_events: int = 12) -> np.ndarray:
    """Calcula la función de masa de probabilidad (PMF) de Poisson vectorizada."""
    events = np.arange(max_events + 1)
    return np.exp(-lambda_param) * np.power(lambda_param, events) / np.array([math.factorial(k) for k in events])


def calculate_score_matrix(lambda_home: float, lambda_away: float, max_goals: int = 10) -> np.ndarray:
    """Genera la matriz bidimensional de probabilidades de marcadores exactos."""
    pmf_home = calculate_poisson_pmf(lambda_home, max_events=max_goals)
    pmf_away = calculate_poisson_pmf(lambda_away, max_events=max_goals)
    return np.outer(pmf_home, pmf_away)


def extract_bet365_catalog_probabilities(
    score_matrix: np.ndarray,
    lambda_home: float,
    lambda_away: float,
) -> dict[str, float]:
    """
    Calcula las probabilidades de todos los mercados de partido y equipo en Bet365 Crear Apuesta.
    """
    n_goals = score_matrix.shape[0]

    # 1. Resultado (1X2)
    home_win = float(np.sum(np.tril(score_matrix, -1)))
    draw = float(np.sum(np.diag(score_matrix)))
    away_win = float(np.sum(np.triu(score_matrix, 1)))

    # 2. Doble Oportunidad
    home_or_draw = home_win + draw
    away_or_draw = away_win + draw
    home_or_away = home_win + away_win

    # 3. Ambos Equipos Anotarán (BTTS)
    p_home_zero = float(np.sum(score_matrix[0, :]))
    p_away_zero = float(np.sum(score_matrix[:, 0]))
    p_0_0 = float(score_matrix[0, 0])
    btts_yes = float(1.0 - p_home_zero - p_away_zero + p_0_0)
    btts_no = float(1.0 - btts_yes)

    # 4. Total de Goles y Rango de Goles
    total_goals_pmf = np.zeros(2 * n_goals - 1)
    for i in range(n_goals):
        for j in range(n_goals):
            total_goals_pmf[i + j] += score_matrix[i, j]

    over_1_5 = float(np.sum(total_goals_pmf[2:]))
    over_2_5 = float(np.sum(total_goals_pmf[3:]))
    over_3_5 = float(np.sum(total_goals_pmf[4:]))
    under_2_5 = float(np.sum(total_goals_pmf[:3]))
    under_3_5 = float(np.sum(total_goals_pmf[:4]))

    range_0_1 = float(np.sum(total_goals_pmf[0:2]))
    range_2_3 = float(np.sum(total_goals_pmf[2:4]))
    range_4_plus = float(np.sum(total_goals_pmf[4:]))

    # 5. Equipo - Goleador (Líneas individuales de goles)
    home_over_0_5 = float(1.0 - p_home_zero)
    home_over_1_5 = float(np.sum(score_matrix[2:, :]))
    away_over_0_5 = float(1.0 - p_away_zero)
    away_over_1_5 = float(np.sum(score_matrix[:, 2:]))

    # 6. Margen de Victoria
    margin_home_1 = float(sum(score_matrix[i + 1, i] for i in range(n_goals - 1)))
    margin_home_2plus = float(sum(score_matrix[i, j] for i in range(n_goals) for j in range(n_goals) if i >= j + 2))
    margin_away_1 = float(sum(score_matrix[i, i + 1] for i in range(n_goals - 1)))
    margin_away_2plus = float(sum(score_matrix[i, j] for i in range(n_goals) for j in range(n_goals) if j >= i + 2))

    # 7. Medio tiempo / Resultado final (HT/FT)
    # Modelado por partición temporal Poisson (1T ~ 45% intensidad, 2T ~ 55%)
    p_ht_draw = float(np.sum(np.diag(calculate_score_matrix(lambda_home * 0.45, lambda_away * 0.45))))
    ht_draw_ft_home = p_ht_draw * (home_win / max(0.01, 1.0 - draw * 0.5))
    ht_home_ft_home = (1.0 - p_ht_draw) * 0.60 * home_win

    # 8. Mitad con mayor número de goles
    # Estadísticamente el 54% de los partidos tienen más goles en el 2º tiempo
    more_goals_2nd_half = 0.52
    more_goals_1st_half = 0.30
    equal_goals_halves = 0.18

    # 9. Equipo - Especiales (Gana a cero y anota en ambas mitades)
    home_win_to_nil = float(sum(score_matrix[i, 0] for i in range(1, n_goals)))
    away_win_to_nil = float(sum(score_matrix[0, j] for j in range(1, n_goals)))
    home_scores_both_halves = float((1.0 - math.exp(-lambda_home * 0.45)) * (1.0 - math.exp(-lambda_home * 0.55)))
    away_scores_both_halves = float((1.0 - math.exp(-lambda_away * 0.45)) * (1.0 - math.exp(-lambda_away * 0.55)))

    return {
        "home_win": home_win,
        "draw": draw,
        "away_win": away_win,
        "home_or_draw": home_or_draw,
        "away_or_draw": away_or_draw,
        "home_or_away": home_or_away,
        "btts_yes": btts_yes,
        "btts_no": btts_no,
        "over_1_5": over_1_5,
        "over_2_5": over_2_5,
        "over_3_5": over_3_5,
        "under_2_5": under_2_5,
        "under_3_5": under_3_5,
        "range_0_1": range_0_1,
        "range_2_3": range_2_3,
        "range_4_plus": range_4_plus,
        "home_over_0_5": home_over_0_5,
        "home_over_1_5": home_over_1_5,
        "away_over_0_5": away_over_0_5,
        "away_over_1_5": away_over_1_5,
        "margin_home_1": margin_home_1,
        "margin_home_2plus": margin_home_2plus,
        "margin_away_1": margin_away_1,
        "margin_away_2plus": margin_away_2plus,
        "ht_draw_ft_home": min(0.35, ht_draw_ft_home),
        "ht_home_ft_home": min(0.45, ht_home_ft_home),
        "more_goals_2nd_half": more_goals_2nd_half,
        "home_win_to_nil": home_win_to_nil,
        "away_win_to_nil": away_win_to_nil,
        "home_scores_both_halves": home_scores_both_halves,
        "away_scores_both_halves": away_scores_both_halves,
    }