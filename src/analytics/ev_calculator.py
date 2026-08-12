"""
Módulo de Cálculo de Valor Esperado Positivo (EV+).

Implementa esquemas Pydantic v2 inmutables y funciones de evaluación financiera 
para identificar cuotas desajustadas por el mercado de apuestas.
"""

import logging
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


class BetRecommendationSchema(BaseModel):
    """
    Modelo de representación inmutable de una oportunidad de apuesta evaluada.
    """

    model_config = ConfigDict(frozen=True)

    market_name: str = Field(..., description="Nombre descriptivo del mercado (ej. 'Victoria Local (River Plate)')")
    odds: float = Field(..., gt=1.0, description="Cuota ofrecida por la casa de apuestas")
    implied_prob: float = Field(..., ge=0.0, le=1.0, description="Probabilidad implícita de la cuota (1 / odds)")
    real_prob: float = Field(..., ge=0.0, le=1.0, description="Probabilidad real estimada por el modelo cuantitativo")
    ev_percentage: float = Field(..., description="Porcentaje de Valor Esperado Positivo (+EV)")
    is_recommended: bool = Field(default=False, description="True si supera el umbral mínimo de rentabilidad (+3.0%)")


def calculate_ev(real_prob: float, odds: float) -> float:
    """
    Calcula el porcentaje de Valor Esperado Positivo (+EV) para una probabilidad y cuota dada.

    Fórmula: EV (%) = ((Probabilidad Real * Cuota) - 1.0) * 100

    Args:
        real_prob (float): Probabilidad real estimada (0.0 a 1.0).
        odds (float): Cuotas ofrecidas por la casa de apuestas (odds > 1.0).

    Returns:
        float: Porcentaje EV (ej. 5.4 para +5.4% EV).
    """
    if odds <= 1.0 or real_prob < 0.0:
        return -100.0

    ev = ((real_prob * odds) - 1.0) * 100.0
    return round(ev, 2)


def evaluate_bet(
    market_name: str,
    real_prob: float,
    odds: float,
    min_ev_threshold: float = 3.0,
) -> BetRecommendationSchema:
    """
    Evalúa una cuota contra la probabilidad del modelo predictivo y genera la recomendación.

    Args:
        market_name (str): Nombre del mercado.
        real_prob (float): Probabilidad estimada por el modelo de Poisson.
        odds (float): Cuota de apuestas (Bet365).
        min_ev_threshold (float): Umbral mínimo de EV% requerido (por defecto 3.0%).

    Returns:
        BetRecommendationSchema: Objeto validado con el cálculo de EV.
    """
    implied_prob = round(1.0 / odds if odds > 0 else 0.0, 4)
    ev_percentage = calculate_ev(real_prob, odds)
    is_recommended = ev_percentage >= min_ev_threshold

    return BetRecommendationSchema(
        market_name=market_name,
        odds=round(odds, 2),
        implied_prob=implied_prob,
        real_prob=round(real_prob, 4),
        ev_percentage=ev_percentage,
        is_recommended=is_recommended,
    )
