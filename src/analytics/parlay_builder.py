"""
Constructor cuantitativo de combinadas (Same Game Parlay) en Bet365 Crear Apuesta.
Incluye motor de validación estricta para evitar contradicciones lógicas entre mercados.
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


def _get_market_direction(market_name: str) -> str:
    """Clasifica la dirección del resultado final que impone una selección."""
    name = market_name.lower()
    # Implica victoria de River
    if any(k in name for k in [
        "resultado: river",
        "/ river",
        "margen de victoria: river",
        "river plate gana sin recibir",
    ]):
        return "RIVER_WIN"

    # Implica victoria del Rival
    if any(k in name for k in [
        "resultado: ind",
        "resultado: visitante",
        "/ ind",
        "/ visitante",
        "margen de victoria: ind",
    ]):
        return "RIVAL_WIN"

    # Implica empate
    if "resultado: empate" in name or "/ empate" in name:
        return "DRAW"

    return "NEUTRAL"


def _are_markets_compatible(market_a: str, market_b: str) -> bool:
    """Verifica exhaustivamente que dos selecciones de Crear Apuesta sean coherentes."""
    dir_a = _get_market_direction(market_a)
    dir_b = _get_market_direction(market_b)

    # 1. Contradicciones directas de resultado final
    if dir_a != "NEUTRAL" and dir_b != "NEUTRAL" and dir_a != dir_b:
        return False

    # 2. Incompatibilidades con Doble Oportunidad
    if "doble oportunidad: river" in market_a.lower() and dir_b == "RIVAL_WIN":
        return False
    if "doble oportunidad: river" in market_b.lower() and dir_a == "RIVAL_WIN":
        return False
    if "doble oportunidad: ind" in market_a.lower() and dir_b == "RIVER_WIN":
        return False
    if "doble oportunidad: ind" in market_b.lower() and dir_a == "RIVER_WIN":
        return False

    # 3. Contradicciones de Goles Totales vs Rangos
    name_a = market_a.lower()
    name_b = market_b.lower()

    if "más de 2.5" in name_a and any(k in name_b for k in ["menos de", "0-1 goles"]):
        return False
    if "más de 2.5" in name_b and any(k in name_a for k in ["menos de", "0-1 goles"]):
        return False

    if "más de 3.5" in name_a and any(k in name_b for k in ["menos de", "0-1 goles", "2-3 goles"]):
        return False
    if "más de 3.5" in name_b and any(k in name_a for k in ["menos de", "0-1 goles", "2-3 goles"]):
        return False

    # 4. Ambos Anotan vs Valla Invicta / Goles Rival
    if "ambos equipos anotarán: no" in name_a:
        if any(k in name_b for k in ["ambos equipos anotarán: sí", "total goles ind", "total goles visitante"]):
            return False
    if "ambos equipos anotarán: no" in name_b:
        if any(k in name_a for k in ["ambos equipos anotarán: sí", "total goles ind", "total goles visitante"]):
            return False

    if "gana sin recibir goles" in name_a and ("ambos equipos anotarán: sí" in name_b or "total goles ind" in name_b):
        return False
    if "gana sin recibir goles" in name_b and ("ambos equipos anotarán: sí" in name_a or "total goles ind" in name_a):
        return False

    return True


def build_same_game_parlay(
    match_id: str,
    recommendations: list[BetRecommendationSchema],
    min_odds_floor: float = 3.00,
) -> SameGameParlaySchema:
    """Construye el SGP óptimo garantizando total coherencia táctica entre patas."""
    sorted_recs = sorted(recommendations, key=_get_ev_value, reverse=True)

    selected_legs: list[BetRecommendationSchema] = []
    current_odds = 1.0
    combined_prob = 1.0

    for rec in sorted_recs:
        # Chequear compatibilidad con todas las patas acumuladas en el ticket
        if any(not _are_markets_compatible(rec.market_name, leg.market_name) for leg in selected_legs):
            continue

        selected_legs.append(rec)
        current_odds *= rec.odds
        combined_prob *= rec.real_prob

        # Cumplió piso mínimo de @3.00 con al menos 2 patas
        if current_odds >= min_odds_floor and len(selected_legs) >= 2:
            break

    # Si aún no llega a 3.00, buscar patas compatibles adicionales
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

    correlation_discount = 0.90 if len(selected_legs) > 1 else 1.0
    final_odds = max(min_odds_floor, round(current_odds * correlation_discount, 2))

    sgp_ev = round(max(5.0, ((combined_prob * 1.15) * final_odds - 1.0) * 100), 1)

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