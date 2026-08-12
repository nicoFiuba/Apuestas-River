import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def calculate_kelly_stake(
    bankroll: float,
    odds: float,
    real_prob: float,
    fraction: float = 0.25,
    min_stake: float = 15.0
) -> dict:
    """
    Calcula el stake óptimo usando el Criterio de Kelly Fraccionado.
    
    :param bankroll: Capital total disponible en ARS (ej: 10000)
    :param odds: Cuota de la casa de apuestas (ej: 2.40)
    :param real_prob: Probabilidad estimada (ej: 0.52)
    :param fraction: Fracción de Kelly para control de riesgo (0.25 = 25% Kelly)
    :param min_stake: Apuesta mínima permitida en la casa (ej: 15.0 ARS en Bet365)
    :return: Diccionario con el stake en ARS, porcentaje del bank y sugerencia final.
    """
    b = odds - 1.0  # Ganancia neta por unidad apostada
    q = 1.0 - real_prob  # Probabilidad de perder
    
    # Kelly puro f* = (bp - q) / b
    f_kelly = ((b * real_prob) - q) / b

    if f_kelly <= 0:
        return {
            "stake_ars": 0.0,
            "bank_percentage": 0.0,
            "recommended_stake": 0.0,
            "is_valid": False
        }

    # Aplicar Kelly fraccionado
    f_adjusted = f_kelly * fraction
    suggested_stake = bankroll * f_adjusted

    # Ajustar a la apuesta mínima si aplica
    final_stake = max(suggested_stake, min_stake) if suggested_stake > 0 else 0.0

    return {
        "stake_ars": round(final_stake, 2),
        "bank_percentage": round(f_adjusted * 100.0, 2),
        "kelly_raw_percentage": round(f_kelly * 100.0, 2),
        "is_valid": final_stake >= min_stake
    }
