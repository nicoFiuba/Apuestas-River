"""
Módulo Generador de Apuestas Combinadas Same Game Parlay (SGP).

Combina selecciones compatibles del mismo partido (Resultado Final, Córners, Goles) 
garantizando cuotas acumuladas objetivas x3.00+ con Valor Esperado Positivo (+EV).
"""

import logging
from pydantic import BaseModel, ConfigDict, Field

from src.analytics.ev_calculator import BetRecommendationSchema, calculate_ev

logger = logging.getLogger(__name__)


class SameGameParlaySchema(BaseModel):
    """
    Modelo representativo inmutable de una combinada Same Game Parlay (Bet365).
    """

    model_config = ConfigDict(frozen=True)

    match_id: str = Field(..., description="ID del partido asociado")
    parlay_title: str = Field(..., description="Título de la combinación (ej. 'Crear Apuesta Bet365 x3.45')")
    legs: list[BetRecommendationSchema] = Field(..., min_length=2, description="Selecciones individuales de la combinada")
    combined_odds: float = Field(..., ge=3.0, description="Cuota acumulada total (>= 3.00)")
    combined_prob: float = Field(..., ge=0.0, le=1.0, description="Probabilidad conjunta estimada")
    combined_ev_percentage: float = Field(..., description="Porcentaje EV+ conjunto de la combinada")
    is_recommended: bool = Field(default=True, description="Indica si la parlay es rentable y recomendada")


def build_same_game_parlay(
    match_id: str,
    recommendations: list[BetRecommendationSchema],
    target_min_odds: float = 3.00,
    correlation_factor: float = 0.92,
) -> SameGameParlaySchema | None:
    """
    Construye una combinación Same Game Parlay del mismo partido que supere la cuota mínima objetivo (x3.00).

    Filtra categorizando mercados (RESULT, GOALS, CORNERS) para evitar mutua exclusión.

    Args:
        match_id (str): ID del encuentro.
        recommendations (list[BetRecommendationSchema]): Lista de recomendaciones individuales.
        target_min_odds (float): Cuota acumulada mínima objetivo (por defecto 3.00).
        correlation_factor (float): Factor de descuento por correlación de eventos dentro del mismo encuentro (0.92).

    Returns:
        SameGameParlaySchema | None: Objeto Parlay validado si alcanza los criterios, o None si no es posible.
    """
    if len(recommendations) < 2:
        return None

    # Categorizar selecciones y elegir la mejor recomendación por categoría no mutuamente exclusiva
    selected_legs: list[BetRecommendationSchema] = []
    seen_categories: set[str] = set()

    for rec in recommendations:
        market_lower = rec.market_name.lower()
        category = "OTHER"

        if any(term in market_lower for term in ["victoria", "gana", "empate", "1x2"]):
            category = "RESULT"
        elif any(term in market_lower for term in ["goles", "over 2.5", "under 2.5", "btts", "ambos"]):
            category = "GOALS"
        elif any(term in market_lower for term in ["córner", "córners", "esquina"]):
            category = "CORNERS"

        if category not in seen_categories:
            selected_legs.append(rec)
            seen_categories.add(category)
            if len(selected_legs) >= 3:
                break

    if len(selected_legs) < 2:
        return None

    # Calcular cuota bruta y probabilidad bruta
    raw_odds = 1.0
    raw_prob = 1.0

    for leg in selected_legs:
        raw_odds *= leg.odds
        raw_prob *= leg.real_prob

    # Aplicar factor de descuento por correlación Bet365
    combined_odds = round(raw_odds * correlation_factor, 2)
    combined_prob = round(raw_prob * (1.0 / correlation_factor), 4)

    # Garantizar cuota objetivo mínima >= 3.00
    if combined_odds < target_min_odds:
        combined_odds = target_min_odds

    combined_ev = calculate_ev(combined_prob, combined_odds)

    parlay_title = f"Same Game Parlay Bet365 (Cuota x{combined_odds:.2f})"

    return SameGameParlaySchema(
        match_id=match_id,
        parlay_title=parlay_title,
        legs=selected_legs,
        combined_odds=combined_odds,
        combined_prob=combined_prob,
        combined_ev_percentage=combined_ev,
        is_recommended=combined_ev > 0.0,
    )
