import math
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def poisson_probability(lmbda: float, k: int) -> float:
    return (math.pow(lmbda, k) * math.exp(-lmbda)) / math.factorial(k)


def generate_score_matrix(lambda_river: float, lambda_rival: float, max_goals: int = 6) -> list[list[float]]:
    """Genera la matriz de probabilidad para cada marcador exacto (River vs Rival)."""
    matrix = []
    for r in range(max_goals + 1):
        row = []
        p_r = poisson_probability(lambda_river, r)
        for v in range(max_goals + 1):
            p_v = poisson_probability(lambda_rival, v)
            row.append(p_r * p_v)
        matrix.append(row)
    return matrix


def evaluate_market_combination(matrix: list[list[float]], conditions: list) -> float:
    """
    Calcula la probabilidad conjunta exacta sumando las celdas (r, v)
    de la matriz que cumplen TODAS las condiciones de la apuesta.
    """
    total_prob = 0.0
    max_goals = len(matrix) - 1

    for r in range(max_goals + 1):
        for v in range(max_goals + 1):
            # Evaluar si la celda (r, v) satisface todas las condiciones
            match_all = True
            for cond in conditions:
                if not cond(r, v):
                    match_all = False
                    break
            if match_all:
                total_prob += matrix[r][v]

    return round(total_prob, 4)


# Definición de Predicados/Condiciones de Mercado (r = Goles River, v = Goles Rival)
CONDITIONS = {
    "RIVER_WIN": lambda r, v: r > v,
    "DRAW": lambda r, v: r == v,
    "RIVAL_WIN": lambda r, v: v > r,
    "RIVER_1X": lambda r, v: r >= v,
    "OVER_15": lambda r, v: (r + v) > 1.5,
    "OVER_25": lambda r, v: (r + v) > 2.5,
    "OVER_35": lambda r, v: (r + v) > 3.5,
    "UNDER_25": lambda r, v: (r + v) < 2.5,
    "UNDER_35": lambda r, v: (r + v) < 3.5,
    "BTTS_YES": lambda r, v: r > 0 and v > 0,
    "BTTS_NO": lambda r, v: r == 0 or v == 0,
    "RIVER_OVER_15": lambda r, v: r > 1.5,
    "RIVER_OVER_25": lambda r, v: r > 2.5,
    "RIVER_WIN_CLEAN": lambda r, v: r > v and v == 0,
}


def calculate_poisson_lambdas(
    home_attack: float,
    home_defense: float,
    away_attack: float,
    away_defense: float,
    is_river_home: bool,
    league_avg_home: float = 1.32,
    league_avg_away: float = 1.05
) -> tuple[float, float]:
    if is_river_home:
        lambda_river = home_attack * away_defense * league_avg_home
        lambda_rival = away_attack * home_defense * league_avg_away
    else:
        lambda_river = away_attack * home_defense * league_avg_away
        lambda_rival = home_attack * away_defense * league_avg_home

    return round(lambda_river, 2), round(lambda_rival, 2)
