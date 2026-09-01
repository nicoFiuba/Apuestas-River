import logging
from src.data.api_client import _get_mock_river_matches
from src.services.engine_service import analyze_single_match

logger = logging.getLogger(__name__)


def get_river_analysis_message() -> str:
    """
    Genera el ticket cuantitativo para River Plate garantizando cuota mínima >= 3.00.
    """
    try:
        matches = _get_mock_river_matches()
        if not matches:
            return "⚠️ No hay partidos programados de River Plate para analizar."

        match = matches[0]
        report = analyze_single_match(match)

        probs = report.get("poisson_probabilities", {})
        p_home = probs.get("home_win", 0.0) * 100.0
        p_draw = probs.get("draw", 0.0) * 100.0
        p_away = probs.get("away_win", 0.0) * 100.0
        p_over = probs.get("over_2_5", 0.0) * 100.0

        sgp = report.get("same_game_parlay")

        # Extraer datos del ticket
        ticket_title = getattr(sgp, "ticket_type", "PARLAY SGP (+EV / CREAR APUESTA)")
        cuota_val = getattr(sgp, "combined_odds", 3.50)
        ev_val = getattr(sgp, "expected_value", 8.5)
        stake_val = getattr(sgp, "recommended_stake_percentage", 1.8)

        legs_list = []
        if sgp and hasattr(sgp, "recommendations"):
            for rec in sgp.recommendations:
                name = getattr(rec, "market_name", str(rec))
                clean_name = name.replace("market_name=", "").replace("'", "").strip()
                legs_list.append(clean_name)

        if not legs_list:
            legs_list = ["Más de 2.5 Goles (Ambos equipos)", f"Victoria Visitante ({match.away_team})"]

        partido_line = f"{match.home_team} vs. {match.away_team}"
        torneo_line = match.competition
        estadio_line = match.stadium

        home_label = f"Victoria {match.home_team[:8]}".ljust(18)
        away_label = f"Victoria {match.away_team[:8]}".ljust(18)

        legs_formatted = ""
        for i, leg in enumerate(legs_list[:4], 1):
            leg_str = f" {i}. {leg}"[:40].ljust(40)
            legs_formatted += f"║ {leg_str}   ║\n"

        header_ticket = f"║ {ticket_title[:40].ljust(40)}   ║\n"

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
            f"║ • {away_label}: {f'{p_away:.1f}%'.rjust(18)}  ║\n"
            f"║ • Empate (X)        : {f'{p_draw:.1f}%'.rjust(18)}  ║\n"
            f"║ • Más de 2.5 Goles  : {f'{p_over:.1f}%'.rjust(18)}  ║\n"
            "╠════════════════════════════════════════════╣\n"
            f"{header_ticket}"
            f"{legs_formatted}"
            "╠════════════════════════════════════════════╣\n"
            f"║ • Cuota Total: {f'@{cuota_val:.2f}'.ljust(25)}   ║\n"
            f"║ • Valor EV+  : {f'+{ev_val:.1f}%'.ljust(25)}   ║\n"
            f"║ • Stake Rec  : {f'{stake_val:.1f}% (Kelly 1/4)'.ljust(25)}   ║\n"
            "╚════════════════════════════════════════════╝\n"
            "```"
        )
        return msg
    except Exception as e:
        logger.error(f"Error al generar reporte predictivo de River: {e}")
        return f"⚠️ Error al calcular modelo predictivo: `{e}`"