"""
Módulo de cálculo de probabilidades mediante Distribución de Poisson vectorizada.
"""

import math
import numpy as np


def calculate_poisson_pmf(lambda_param: float, max_events: int = 15) -> np.ndarray:
    """Calcula la función de masa de probabilidad (PMF) de Poisson vectorizada."""
    events = np.arange(max_events + 1)
    return np.exp(-lambda_param) * np.power(lambda_param, events) / np.array([math.factorial(k) for k in events])


def calculate_score_matrix(lambda_home: float, lambda_away: float, max_goals: int = 10) -> np.ndarray:
    """Genera la matriz bidimensional de probabilidades de marcadores exactos."""
    pmf_home = calculate_poisson_pmf(lambda_home, max_events=max_goals)
    pmf_away = calculate_poisson_pmf(lambda_away, max_events=max_goals)
    return np.outer(pmf_home, pmf_away)


def extract_match_probabilities(score_matrix: np.ndarray, is_river_away: bool = False) -> dict[str, float]:
    """Extrae probabilidades acumuladas de 1X2, dobles oportunidades, líneas de goles y BTTS."""
    home_win = float(np.sum(np.tril(score_matrix, -1)))
    draw = float(np.sum(np.diag(score_matrix)))
    away_win = float(np.sum(np.triu(score_matrix, 1)))

    home_or_draw = home_win + draw
    away_or_draw = away_win + draw

    total_goals_matrix = np.zeros(score_matrix.shape[0] + score_matrix.shape[1] - 1)
    for i in range(score_matrix.shape[0]):
        for j in range(score_matrix.shape[1]):
            total_goals_matrix[i + j] += score_matrix[i, j]

    over_1_5 = float(np.sum(total_goals_matrix[2:]))
    over_2_5 = float(np.sum(total_goals_matrix[3:]))
    over_3_5 = float(np.sum(total_goals_matrix[4:]))

    p_home_zero = float(np.sum(score_matrix[0, :]))
    p_away_zero = float(np.sum(score_matrix[:, 0]))
    p_0_0 = float(score_matrix[0, 0])
    btts_yes = float(1.0 - p_home_zero - p_away_zero + p_0_0)
    btts_no = float(1.0 - btts_yes)

    if is_river_away:
        river_over_0_5 = float(1.0 - p_away_zero)
        river_over_1_5 = float(np.sum(score_matrix[:, 2:]))
        margin_river_2plus = float(sum(score_matrix[i, j] for i in range(score_matrix.shape[0]) for j in range(i + 2, score_matrix.shape[1])))
    else:
        river_over_0_5 = float(1.0 - p_home_zero)
        river_over_1_5 = float(np.sum(score_matrix[2:, :]))
        margin_river_2plus = float(sum(score_matrix[i, j] for i in range(score_matrix.shape[0]) for j in range(score_matrix.shape[1]) if i >= j + 2))

    return {
        "home_win": home_win,
        "draw": draw,
        "away_win": away_win,
        "home_or_draw": home_or_draw,
        "away_or_draw": away_or_draw,
        "over_1_5": over_1_5,
        "over_2_5": over_2_5,
        "over_3_5": over_3_5,
        "btts_yes": btts_yes,
        "btts_no": btts_no,
        "river_over_0_5": river_over_0_5,
        "river_over_1_5": river_over_1_5,
        "margin_river_2plus": margin_river_2plus,
    }


def calculate_corner_probabilities(expected_home_corners: float, expected_away_corners: float) -> dict[str, float]:
    """Calcula probabilidades para mercados de tiros de esquina."""
    total_corners_lambda = expected_home_corners + expected_away_corners
    pmf_total = calculate_poisson_pmf(total_corners_lambda, max_events=25)
    return {
        "over_8_5_corners": float(np.sum(pmf_total[9:])),
        "over_9_5_corners": float(np.sum(pmf_total[10:])),
    }


def calculate_discipline_and_fouls_probabilities(
    expected_cards: float = 4.8,
    expected_reds: float = 0.22,
    expected_fouls: float = 26.0,
) -> dict[str, float]:
    """Calcula probabilidades de tarjetas, faltas y expulsiones."""
    pmf_cards = calculate_poisson_pmf(expected_cards, max_events=15)
    pmf_fouls = calculate_poisson_pmf(expected_fouls, max_events=45)
    return {
        "over_4_5_cards": float(np.sum(pmf_cards[5:])),
        "over_23_5_fouls": float(np.sum(pmf_fouls[24:])),
    }