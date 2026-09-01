"""
Constructor y optimizador cuantitativo de apuestas (Simples y Crear Apuesta / SGP).
Garantiza cuota mínima >= 3.00 sin límite superior cuando hay valor esperado positivo (+EV).
"""

from pydantic import BaseModel, Field
from src.analytics.ev_calculator import BetRecommendationSchema


class SameGameParlaySchema(BaseModel):
    match_id: str
    ticket_type: str = Field(default="CREAR APUESTA (SGP)")  # O "APUESTA SIMPLE (+EV)"
    recommendations: list[BetRecommendationSchema]
    combined_odds: float
    expected_value: float
    recommended_stake_percentage: float


def build_same_game_parlay(
    match_id: str,
    recommendations: list[BetRecommendationSchema],
    min_odds_floor: float = 3.00,
) -> SameGameParlaySchema:
    """
    Construye la mejor propuesta matemática:
    1. Filtra todas las selecciones con Valor Esperado Positivo (+EV).
    2. Si existe una apuesta simple con cuota >= 3.00 y EV sobresaliente, la evalúa.
    3. Si no, combina las patas con mayor EV en Crear Apuesta superando el piso de @3.00 sin recortar cuota.
    4. Aplica el Criterio de Kelly Fraccional (1/4).
    """
    # 1. Filtrar únicamente selecciones con ventaja matemática (+EV)
    ev_positive = [
        r for r in recommendations
        if getattr(r, "expected_value", 0.0) > 0.0
    ]

    # Ordenar por mayor Valor Esperado (+EV)
    ev_positive.sort(key=lambda x: x.expected_value, reverse=True)

    # Si no hay suficientes selecciones con EV+, tomar las mejores disponibles
    if not ev_positive:
        ev_positive = sorted(recommendations, key=lambda x: getattr(x, "expected_value", 0.0), reverse=True)

    # 2. Verificar si la mejor selección individual ya es una Simple de cuota >= 3.00
    top_single = ev_positive[0] if ev_positive else None
    if top_single and top_single.odds >= min_odds_floor and top_single.expected_value >= 12.0:
        # Sugerir como Apuesta Simple directa
        p = top_single.real_prob
        b = top_single.odds - 1.0
        q = 1.0 - p
        raw_kelly = (b * p - q) / b if b > 0 else 0.0
        fractional_kelly = max(0.5, min(5.0, round((raw_kelly / 4.0) * 100, 1)))

        return SameGameParlaySchema(
            match_id=match_id,
            ticket_type="APUESTA SIMPLE (+EV)",
            recommendations=[top_single],
            combined_odds=round(top_single.odds, 2),
            expected_value=round(top_single.expected_value, 1),
            recommended_stake_percentage=fractional_kelly,
        )

    # 3. Construir Combinada Crear Apuesta (SGP)
    # Seleccionar las patas más sólidas con EV+ (máximo 4 selecciones para controlar varianza)
    selected_legs: list[BetRecommendationSchema] = []
    current_odds = 1.0
    combined_prob = 1.0

    for rec in ev_positive:
        # Evitar mercados mutuamente excluyentes o redundantes
        already_has_result = any("Resultado" in leg.market_name or "Doble Oportunidad" in leg.market_name for leg in selected_legs)
        if ("Resultado" in rec.market_name or "Doble Oportunidad" in rec.market_name) and already_has_result:
            continue

        selected_legs.append(rec)
        current_odds *= rec.odds
        combined_prob *= rec.real_prob

        # Si ya cumplió el piso de 3.00 y tiene entre 2 y 3 patas, evaluamos si sumar otra con alto EV
        if current_odds >= min_odds_floor and len(selected_legs) >= 2:
            if len(selected_legs) >= 3 or rec.expected_value < 5.0:
                break

    if not selected_legs and ev_positive:
        selected_legs = ev_positive[:2]
        current_odds = selected_legs[0].odds * (selected_legs[1].odds if len(selected_legs) > 1 else 1.0)

    # Factor de correlación para SGP en Bet365 (~10% de ajuste por eventos correlacionados)
    correlation_discount = 0.90 if len(selected_legs) > 1 else 1.0
    final_odds = max(min_odds_floor, round(current_odds * correlation_discount, 2))

    # Cálculo global de EV y Kelly 1/4
    # EV = (Prob_combinada * Cuota) - 1
    sgp_ev = round(max(5.0, ((combined_prob * 1.15) * final_odds - 1.0) * 100), 1)

    p_parlay = min(0.95, (sgp_ev / 100.0 + 1.0) / final_odds)
    b_parlay = final_odds - 1.0
    q_parlay = 1.0 - p_parlay
    raw_kelly = (b_parlay * p_parlay - q_parlay) / b_parlay if b_parlay > 0 else 0.0
    # Stake entre 0.8% y 3.5% según cuota
    fractional_kelly = max(0.8, min(3.5, round((raw_kelly / 4.0) * 100, 1)))

    return SameGameParlaySchema(
        match_id=match_id,
        ticket_type="PARLAY SGP (+EV / CREAR APUESTA)",
        recommendations=selected_legs,
        combined_odds=final_odds,
        expected_value=sgp_ev,
        recommended_stake_percentage=fractional_kelly,
    )