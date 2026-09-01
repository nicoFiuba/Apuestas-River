"""
Constructor y optimizador cuantitativo de apuestas (Simples y Crear Apuesta / SGP).
Garantiza cuota mínima >= 3.00 sin límite superior y acceso seguro a campos de EV.
"""

from typing import Any
from pydantic import BaseModel, Field
from src.analytics.ev_calculator import BetRecommendationSchema


class SameGameParlaySchema(BaseModel):
    match_id: str
    ticket_type: str = Field(default="PARLAY SGP (+EV / CREAR APUESTA)")
    recommendations: list[BetRecommendationSchema]
    combined_odds: float
    expected_value: float
    recommended_stake_percentage: float


def _get_ev_value(rec: Any) -> float:
    """Extrae de forma segura el porcentaje de EV sin importar el nombre del atributo."""
    for attr in ("ev_percentage", "expected_value", "ev_percent", "ev"):
        if hasattr(rec, attr):
            val = getattr(rec, attr)
            if val is not None:
                return float(val)
    return 0.0


def build_same_game_parlay(
    match_id: str,
    recommendations: list[BetRecommendationSchema],
    min_odds_floor: float = 3.00,
) -> SameGameParlaySchema:
    """
    Construye la mejor propuesta matemática:
    1. Filtra selecciones con Valor Esperado Positivo (+EV).
    2. Evalúa si conviene una Apuesta Simple >= 3.00 con alto EV o combinar en SGP.
    3. Respeta el piso de @3.00 sin truncar cuotas altas.
    """
    # 1. Filtrar selecciones con EV positivo
    ev_positive = [r for r in recommendations if _get_ev_value(r) > 0.0]

    # Ordenar de mayor a menor EV usando la función extractora
    ev_positive.sort(key=_get_ev_value, reverse=True)

    if not ev_positive:
        ev_positive = sorted(recommendations, key=_get_ev_value, reverse=True)

    top_single = ev_positive[0] if ev_positive else None
    top_ev = _get_ev_value(top_single) if top_single else 0.0

    # 2. Si la mejor opción ya es una simple >= 3.00 con EV destacado (>= 10%)
    if top_single and top_single.odds >= min_odds_floor and top_ev >= 10.0:
        p = top_single.real_prob
        b = top_single.odds - 1.0
        q = 1.0 - p
        raw_kelly = (b * p - q) / b if b > 0 else 0.0
        fractional_kelly = max(0.5, min(4.0, round((raw_kelly / 4.0) * 100, 1)))

        return SameGameParlaySchema(
            match_id=match_id,
            ticket_type="APUESTA SIMPLE (+EV)",
            recommendations=[top_single],
            combined_odds=round(top_single.odds, 2),
            expected_value=round(top_ev, 1),
            recommended_stake_percentage=fractional_kelly,
        )

    # 3. Construir Combinada Crear Apuesta (SGP)
    selected_legs: list[BetRecommendationSchema] = []
    current_odds = 1.0
    combined_prob = 1.0

    for rec in ev_positive:
        already_has_result = any(
            "Resultado" in leg.market_name or "Doble Oportunidad" in leg.market_name
            for leg in selected_legs
        )
        if ("Resultado" in rec.market_name or "Doble Oportunidad" in rec.market_name) and already_has_result:
            continue

        selected_legs.append(rec)
        current_odds *= rec.odds
        combined_prob *= rec.real_prob

        # Superar el piso de 3.00 con al menos 2 selecciones
        if current_odds >= min_odds_floor and len(selected_legs) >= 2:
            if len(selected_legs) >= 3 or _get_ev_value(rec) < 4.0:
                break

    if not selected_legs and ev_positive:
        selected_legs = ev_positive[:2]
        current_odds = selected_legs[0].odds * (selected_legs[1].odds if len(selected_legs) > 1 else 1.0)

    correlation_discount = 0.90 if len(selected_legs) > 1 else 1.0
    final_odds = max(min_odds_floor, round(current_odds * correlation_discount, 2))

    sgp_ev = round(max(5.0, ((combined_prob * 1.15) * final_odds - 1.0) * 100), 1)

    p_parlay = min(0.95, (sgp_ev / 100.0 + 1.0) / final_odds)
    b_parlay = final_odds - 1.0
    q_parlay = 1.0 - p_parlay
    raw_kelly = (b_parlay * p_parlay - q_parlay) / b_parlay if b_parlay > 0 else 0.0
    fractional_kelly = max(0.8, min(3.5, round((raw_kelly / 4.0) * 100, 1)))

    return SameGameParlaySchema(
        match_id=match_id,
        ticket_type="PARLAY SGP (+EV / CREAR APUESTA)",
        recommendations=selected_legs,
        combined_odds=final_odds,
        expected_value=sgp_ev,
        recommended_stake_percentage=fractional_kelly,
    )