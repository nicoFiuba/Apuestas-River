"""
Pruebas unitarias para los módulos de Inferencia Cuantitativa (Poisson, EV+ & Same Game Parlay).
"""

import pytest
import numpy as np

from src.analytics.poisson import (
    calculate_poisson_pmf,
    calculate_score_matrix,
    extract_match_probabilities,
    calculate_corner_probabilities,
)
from src.analytics.ev_calculator import calculate_ev, evaluate_bet
from src.analytics.parlay_builder import build_same_game_parlay


def test_poisson_pmf_normalized() -> None:
    """Valida que la PMF de Poisson sume exactamente 1.0."""
    pmf = calculate_poisson_pmf(lambda_param=2.10, max_goals=10)
    assert isinstance(pmf, np.ndarray)
    assert len(pmf) == 11
    assert pytest.approx(float(np.sum(pmf)), 1e-4) == 1.0


def test_score_matrix_structure() -> None:
    """Valida que la matriz de marcadores sea 11x11 y sume 1.0."""
    matrix = calculate_score_matrix(lambda_home=2.10, lambda_away=0.85, max_goals=10)
    assert matrix.shape == (11, 11)
    assert pytest.approx(float(np.sum(matrix)), 1e-4) == 1.0


def test_extract_match_probabilities_sums() -> None:
    """Valida que 1X2 sea consistente (Local + Empate + Visita ~ 1.0)."""
    matrix = calculate_score_matrix(lambda_home=2.10, lambda_away=0.85, max_goals=10)
    probs = extract_match_probabilities(matrix)

    total_1x2 = probs["home_win"] + probs["draw"] + probs["away_win"]
    assert pytest.approx(total_1x2, 1e-2) == 1.0
    assert "over_2_5" in probs
    assert "under_2_5" in probs


def test_calculate_ev_formula() -> None:
    """Valida la fórmula de Valor Esperado Positivo (+EV)."""
    # Prob real 0.55 * Cuota 2.0 = 1.10 -> EV = +10.0%
    ev = calculate_ev(real_prob=0.55, odds=2.0)
    assert ev == 10.0

    # Prob real 0.40 * Cuota 2.0 = 0.80 -> EV = -20.0%
    ev_neg = calculate_ev(real_prob=0.40, odds=2.0)
    assert ev_neg == -20.0


def test_evaluate_bet_threshold() -> None:
    """Valida el filtrado según el umbral mínimo de EV+ (3.0%)."""
    rec_recommended = evaluate_bet("Mercado EV+", real_prob=0.55, odds=1.95, min_ev_threshold=3.0)
    assert rec_recommended.is_recommended is True
    assert rec_recommended.ev_percentage > 3.0

    rec_not = evaluate_bet("Mercado sin valor", real_prob=0.45, odds=1.90, min_ev_threshold=3.0)
    assert rec_not.is_recommended is False


def test_build_same_game_parlay_target_odds() -> None:
    """Valida que la parlay combinada alcance o supere la cuota x3.00."""
    rec1 = evaluate_bet("River Plate Gana", real_prob=0.60, odds=1.90)
    rec2 = evaluate_bet("Más de 9.5 Córners", real_prob=0.58, odds=1.85)

    parlay = build_same_game_parlay("RIV-2026-001", [rec1, rec2], target_min_odds=3.00)

    assert parlay is not None
    assert parlay.combined_odds >= 3.00
    assert len(parlay.legs) == 2
    assert "Same Game Parlay" in parlay.parlay_title
