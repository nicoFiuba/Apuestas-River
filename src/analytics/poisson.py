"""
Módulo de Inferencia Estadística mediante Distribución de Poisson.

Proporciona funciones puras utilizando numpy y math para la generación 
de matrices de probabilidad de marcadores exactos y mercados derivados.
"""

import math
import numpy as np


def calculate_poisson_pmf(lambda_param: float, max_goals: int = 10) -> np.ndarray:
    """
    Calcula la Función de Masa de Probabilidad (PMF) de Poisson vectorizada.

    Args:
        lambda_param (float): Esperanza matemática de goles (lambda > 0).
        max_goals (int): Límite máximo de goles a considerar (por defecto 10).

    Returns:
        np.ndarray: Vector 1D con las probabilidades P(k) para k in [0, max_goals].
    """
    if lambda_param <= 0:
        lambda_param = 0.01

    goals = np.arange(0, max_goals + 1)
    factorials = np.array([math.factorial(k) for k in goals], dtype=np.float64)
    pmf = (np.power(lambda_param, goals) * math.exp(-lambda_param)) / factorials
    return pmf / np.sum(pmf)  # Normalización


def calculate_score_matrix(
    lambda_home: float, lambda_away: float, max_goals: int = 10
) -> np.ndarray:
    """
    Calcula la matriz bidimensional de probabilidades de marcadores exactos.

    P(home=i, away=j) = P_home(i) * P_away(j)

    Args:
        lambda_home (float): Goles esperados del equipo local.
        lambda_away (float): Goles esperados del equipo visitante.
        max_goals (int): Límite superior de goles por equipo.

    Returns:
        np.ndarray: Matriz (max_goals+1, max_goals+1) de probabilidades.
    """
    pmf_home = calculate_poisson_pmf(lambda_home, max_goals)
    pmf_away = calculate_poisson_pmf(lambda_away, max_goals)

    # Producto exterior de ambos vectores PMF
    score_matrix = np.outer(pmf_home, pmf_away)
    return score_matrix / np.sum(score_matrix)


def extract_match_probabilities(score_matrix: np.ndarray) -> dict[str, float]:
    """
    Extrae las probabilidades agregadas de los mercados principales a partir de la matriz de marcadores.

    Args:
        score_matrix (np.ndarray): Matriz bidimensional de marcadores.

    Returns:
        dict[str, float]: Probabilidades para home_win, draw, away_win, over_2_5, under_2_5, btts.
    """
    rows, cols = score_matrix.shape

    # 1. Mercado 1X2
    home_win_prob = float(np.sum(np.tril(score_matrix, -1)))
    draw_prob = float(np.sum(np.diag(score_matrix)))
    away_win_prob = float(np.sum(np.triu(score_matrix, 1)))

    # 2. Mercado Goles (Over/Under 2.5)
    over_2_5_prob = 0.0
    under_2_5_prob = 0.0

    for i in range(rows):
        for j in range(cols):
            prob = float(score_matrix[i, j])
            if i + j > 2.5:
                over_2_5_prob += prob
            else:
                under_2_5_prob += prob

    # 3. Both Teams To Score (BTTS)
    btts_prob = float(np.sum(score_matrix[1:, 1:]))

    return {
        "home_win": round(home_win_prob, 4),
        "draw": round(draw_prob, 4),
        "away_win": round(away_win_prob, 4),
        "over_2_5": round(over_2_5_prob, 4),
        "under_2_5": round(under_2_5_prob, 4),
        "btts": round(btts_prob, 4),
    }


def calculate_corner_probabilities(
    expected_home_corners: float, expected_away_corners: float
) -> dict[str, float]:
    """
    Calcula probabilidades de mercados de tiros de esquina usando Distribución de Poisson en la suma.

    Args:
        expected_home_corners (float): Córners esperados local.
        expected_away_corners (float): Córners esperados visitante.

    Returns:
        dict[str, float]: Probabilidades para over_8_5, over_9_5, over_10_5 córners.
    """
    lambda_total = expected_home_corners + expected_away_corners
    pmf_corners = calculate_poisson_pmf(lambda_total, max_goals=25)

    over_8_5 = float(np.sum(pmf_corners[9:]))
    over_9_5 = float(np.sum(pmf_corners[10:]))
    over_10_5 = float(np.sum(pmf_corners[11:]))

    return {
        "over_8_5_corners": round(over_8_5, 4),
        "over_9_5_corners": round(over_9_5, 4),
        "over_10_5_corners": round(over_10_5, 4),
    }
