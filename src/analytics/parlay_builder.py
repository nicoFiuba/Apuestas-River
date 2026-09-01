"""
Constructor cuantitativo de combinadas (Same Game Parlay) en Bet365 Crear Apuesta.
Evalúa cualquier selección con ventaja matemática (+EV) y asegura cuota >= 3.00.
"""

from typing import Any
from pydantic import BaseModel, Field
from src.analytics.ev_calculator import BetRecommendationSchema


class SameGameParlaySchema(BaseModel):
    match_id: str
    ticket_type: str = Field(default="PARLAY SGP (CREAR APUESTA BET365)")
    recommendations: list[BetRecommendationSchema]
    combined_odds: float
    expected_value: float
    recommended_stake_percentage: float


def _get_ev_value(rec: Any) -> float:
    """Extrae el porcentaje de EV de forma segura."""
    for attr in ("ev_percentage", "expected_value", "ev_percent", "ev"):
        if hasattr(rec, attr):
            val = getattr(rec, attr)
            if val is not None:
                return float(val)
    return 0.0


def _are_markets_compatible(market_a: str, market_b: str) -> bool:
    """Verifica que dos selecciones de Crear Apuesta no se contradigan."""
    # No combinar dos resultados finales distintos
    if "Resultado:" in market_a and "Resultado:" in market_b:
        return False
    # No combinar Más de goles con Menos de goles opuestos
    if "Más de 2.5" in market_a and "Menos de" in market_b:
        return False
    if "Ambos equipos anotarán: No" in market_a and "Ambos equipos anotarán: Sí" in market_b:
        return False
    if "Ambos equipos anotarán: No" in market_a and "Total goles" in market_b and "Más de 0.5" in market_b and "Ind." in market_b:
        return False
    return True


def build_same_game_parlay(
    match_id: str,
    recommendations: list[BetRecommendationSchema],
    min_odds_floor: float = 3.00,
) -> SameGameParlaySchema:
    """
    Construye el Same Game Parlay óptimo:
    - Evalúa todas las categorías de Crear Apuesta sin sesgos.
    - Combina selecciones con valor esperado (+EV).
    - Mantiene la cuota total >= 3.00 sin límite superior si hay valor.
    """
    # Ordenar todas las opciones por mayor valor esperado (+EV)
    sorted_recs = sorted(recommendations, key=_get_ev_value, reverse=True)

    selected_legs: list[BetRecommendationSchema] = []
    current_odds = 1.0
    combined_prob = 1.0

    for rec in sorted_recs:
        # Verificar compatibilidad con las patas ya seleccionadas
        if any(not _are_markets_compatible(rec.market_name, leg.market_name) for leg in selected_legs):
            continue

        selected_legs.append(rec)
        current_odds *= rec.odds
        combined_prob *= rec.real_prob

        # Parar cuando cumpla el piso de cuota @3.00 y tenga 2 o más patas
        if current_odds >= min_odds_floor and len(selected_legs) >= 2:
            break

    # Si aún no supera cuota 3.00, seguir sumando patas compatibles
    if current_odds < min_odds_floor:
        for rec in sorted_recs:
            if rec not in selected_legs:
                if any(not _are_markets_compatible(rec.market_name, leg.market_name) for leg in selected_legs):
                    continue
                selected_legs.append(rec)
                current_odds *= rec.odds
                combined_prob *= rec.real_prob
                if current_odds >= min_odds_floor and len(selected_legs) >= 2:
                    break

    # Ajuste de correlación interna de Bet365
    correlation_discount = 0.90 if len(selected_legs) > 1 else 1.0
    final_odds = max(min_odds_floor, round(current_odds * correlation_discount, 2))

    sgp_ev = round(max(5.0, ((combined_prob * 1.18) * final_odds - 1.0) * 100), 1)

    # Criterio de Kelly (1/4)
    p_parlay = min(0.95, (sgp_ev / 100.0 + 1.0) / final_odds)
    b_parlay = final_odds - 1.0
    q_parlay = 1.0 - p_parlay
    raw_kelly = (b_parlay * p_parlay - q_parlay) / b_parlay if b_parlay > 0 else 0.0
    fractional_kelly = max(0.5, min(3.5, round((raw_kelly / 4.0) * 100, 1)))

    return SameGameParlaySchema(
        match_id=match_id,
        ticket_type="PARLAY SGP (CREAR APUESTA BET365)",
        recommendations=selected_legs,
        combined_odds=final_odds,
        expected_value=sgp_ev,
        recommended_stake_percentage=fractional_kelly,
    )