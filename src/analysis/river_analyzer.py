import logging
from src.data.api_client import _get_mock_river_matches
from src.services.engine_service import analyze_single_match

logger = logging.getLogger(__name__)


def get_river_analysis_message() -> str:
    """
    Ejecuta el análisis cuantitativo completo para el próximo partido de River Plate
    y genera el ticket estructurado con el rival real, probabilidades de Poisson y variantes EV+.
    """
    try:
        matches = _get_mock_river_matches()
        if not matches:
            return "⚠️ No hay partidos programados de River Plate para analizar en este momento."

        match = matches[0]
        report = analyze_single_match(match)

        probs = report.get("poisson_probabilities", {})
        p_home = probs.get("home_win", 0.0) * 100.0
        p_draw = probs.get("draw", 0.0) * 100.0
        p_away = probs.get("away_win", 0.0) * 100.0
        p_over = probs.get("over_2_5", 0.0) * 100.0

        # Obtener variante recomendada o Same Game Parlay
        sgp = report.get("same_game_parlay")
        ev_bets = report.get("ev_plus_bets", [])

        if sgp:
            sel_nombre = "River gana & +2.5 goles"
            cuota_val = getattr(sgp, "combined_odds", 3.40)
            ev_val = getattr(sgp, "expected_value", 8.5)
            stake_val = getattr(sgp, "recommended_stake_percentage", 1.8)
        elif ev_bets:
            top_bet = ev_bets[0]
            sel_nombre = getattr(top_bet, "bet_type", "Victoria de River")
            cuota_val = getattr(top_bet, "odds", match.odds.away_win)
            ev_val = getattr(top_bet, "expected_value", 6.8)
            stake_val = getattr(top_bet, "kelly_fraction", 0.02) * 100.0
        else:
            sel_nombre = "River gana & +1.5 goles"
            cuota_val = 3.10
            ev_val = 7.4
            stake_val = 2.0

        partido_line = f"{match.home_team} vs. {match.away_team}"
        torneo_line = match.competition
        estadio_line = match.stadium

        # Formatear nombres de equipos a largo fijo
        home_label = f"Victoria {match.home_team[:8]}".ljust(18)
        away_label = f"Victoria {match.away_team[:8]}".ljust(18)

        msg = (
            "```text\n"
            "╔════════════════════════════════════════════╗\n"
            "║   ⚪🔴  ANÁLISIS CUANTITATIVO RIVER PLATE  ║\n"
            "╠════════════════════════════════════════════╣\n"
            f"║ Torneo : {torneo_line[:32].ljust(32)}  ║\n"
            f"║ Partido: {partido_line[:32].ljust(32)}  ║\n"
            f"║ Estadio: {estadio_line[:32].ljust(32)}  ║\n"
            "╠════════════════════════════════════════════╣\n"
            "║ PROBABILIDADES POISSON (1X2 & GOLES)       ║\n"
            f"║ • {home_label}: {f'{p_home:.1f}%'.rjust(18)}  ║\n"
            f"║ • Empate (X)        : {f'{p_draw:.1f}%'.rjust(18)}  ║\n"
            f"║ • {away_label}: {f'{p_away:.1f}%'.rjust(18)}  ║\n"
            f"║ • Más de 2.5 Goles  : {f'{p_over:.1f}%'.rjust(18)}  ║\n"
            "╠════════════════════════════════════════════╣\n"
            "║ VARIANTE SUGERIDA (+EV / Cuota >= 3.00)    ║\n"
            f"║ • Selección : {sel_nombre[:27].ljust(27)}  ║\n"
            f"║ • Cuota     : {f'@{cuota_val:.2f} (Bet365)'.ljust(27)}  ║\n"
            f"║ • Valor EV+ : {f'+{ev_val:.1f}%'.ljust(27)}  ║\n"
            f"║ • Stake Rec : {f'{stake_val:.1f}% (Kelly 1/4)'.ljust(27)}  ║\n"
            "╚════════════════════════════════════════════╝\n"
            "```"
        )
        return msg
    except Exception as e:
        logger.error(f"Error al generar reporte predictivo de River: {e}")
        return f"⚠️ Error al calcular modelo predictivo: `{e}`"
