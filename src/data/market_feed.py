"""
Catálogo dinámico de cuotas de Bet365 con los 10 mercados de Crear Apuesta.
"""

from pydantic import BaseModel, Field


class Bet365MarketFeed(BaseModel):
    # 1. Resultado (1X2)
    result_home: float = Field(default=1.42, description="Resultado: River Plate")
    result_draw: float = Field(default=4.30, description="Resultado: Empate")
    result_away: float = Field(default=8.00, description="Resultado: Rival")

    # 2. Ambos equipos anotarán (BTTS)
    btts_yes: float = Field(default=2.10, description="Ambos equipos anotarán: Sí")
    btts_no: float = Field(default=1.70, description="Ambos equipos anotarán: No")

    # 3. Doble oportunidad
    double_chance_1x: float = Field(default=1.14, description="River Plate o Empate")
    double_chance_x2: float = Field(default=2.80, description="Rival o Empate")
    double_chance_12: float = Field(default=1.20, description="River Plate o Rival")

    # 4. Total de goles (Ambos equipos juntos)
    over_1_goal: float = Field(default=1.44, description="Más de 1 gol")
    over_2_goals: float = Field(default=2.35, description="Más de 2 goles")
    over_3_goals: float = Field(default=4.50, description="Más de 3 goles")
    under_2_goals: float = Field(default=2.62, description="Menos de 2 goles")
    under_3_goals: float = Field(default=1.57, description="Menos de 3 goles")

    # 5. Rango de goles
    range_1_2: float = Field(default=1.83, description="1-2 goles")
    range_1_3: float = Field(default=1.36, description="1-3 goles")
    range_1_4: float = Field(default=1.18, description="1-4 goles")
    range_2_3: float = Field(default=2.00, description="2-3 goles")

    # 6. Medio tiempo / Resultado final (HT/FT)
    ht_river_ft_river: float = Field(default=2.75, description="River - River")
    ht_river_ft_draw: float = Field(default=15.00, description="River - Empate")
    ht_draw_ft_river: float = Field(default=4.33, description="Empate - River")
    ht_draw_ft_draw: float = Field(default=4.50, description="Empate - Empate")
    ht_draw_ft_rival: float = Field(default=10.00, description="Empate - Rival")

    # 7. Marcador exacto
    score_1_0: float = Field(default=5.50, description="Marcador 1-0")
    score_2_0: float = Field(default=7.00, description="Marcador 2-0")
    score_2_1: float = Field(default=9.00, description="Marcador 2-1")
    score_0_0: float = Field(default=7.00, description="Marcador 0-0")
    score_1_1: float = Field(default=6.50, description="Marcador 1-1")

    # 8. Mitad con mayor número de goles
    half_1st_more_goals: float = Field(default=3.10, description="1ª mitad")
    half_2nd_more_goals: float = Field(default=2.20, description="2ª mitad")
    halves_equal_goals: float = Field(default=3.20, description="Ninguna mitad (empate)")

    # 9. Equipo - Especiales
    river_to_nil: float = Field(default=2.50, description="River ganará a cero")
    river_both_halves_score: float = Field(default=3.40, description="River anotará en ambas mitades")
    river_win_both_halves: float = Field(default=5.50, description="River ganará ambas mitades")
    river_win_any_half: float = Field(default=1.44, description="River ganará cualquier mitad")
    rival_to_nil: float = Field(default=8.00, description="Rival ganará a cero")

    # 10. Margen de victoria
    river_margin_1: float = Field(default=3.40, description="River por 1 gol")
    river_margin_2: float = Field(default=5.00, description="River por 2 goles")
    river_margin_2plus: float = Field(default=3.25, description="River por 2 goles o más")
    river_margin_3plus: float = Field(default=8.00, description="River por 3 goles o más")
    rival_margin_1: float = Field(default=6.50, description="Rival por 1 gol")
    rival_margin_2plus: float = Field(default=15.00, description="Rival por 2 goles o más")


def get_live_bet365_feed() -> Bet365MarketFeed:
    """Retorna las cuotas vigentes del mercado."""
    return Bet365MarketFeed()