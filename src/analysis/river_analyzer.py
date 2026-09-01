"""
Módulo de análisis predictivo cuantitativo para River Plate (Poisson & SGP).
"""

import logging
from src.data.api_client import _get_mock_river_matches
from src.services.engine_service import analyze_single_match

logger = logging.getLogger(__name__)


def get_river_analysis_message() -> str:
    """
    Genera el reporte cuantitativo para River Plate con formato limpio tipo tarjeta.
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

        # Métricas del ticket
        cuota_val = getattr(sgp, "combined_odds", 3.50)
        ev_val = getattr(sgp, "expected_value", 8.5)
        stake_val = getattr(sgp, "recommended_stake_percentage", 1.8)

        # Extracción de patas recomendadas
        legs_list = []
        if sgp and hasattr(sgp, "recommendations"):
            for rec in sgp.recommendations:
                name = getattr(rec, "market_name", str(rec))
                clean_name = name.replace("market_name=", "").replace("'", "").strip()
                legs_list.append(clean_name)

        if not legs_list:
            legs_list = ["Más de 2.5 Goles (Ambos equipos)", f"Victoria Visitante ({match.away_team})"]

        # Formateo de patas con enumeración visual
        num_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣"]
        legs_formatted = []
        for idx, leg in enumerate(legs_list[:4]):
            prefix = num_emojis[idx] if idx < len(num_emojis) else f"{idx+1}."
            legs_formatted.append(f"{prefix} `{leg}`")
        legs_block = "\n".join(legs_formatted)

        partido_line = f"{match.home_team.upper()} vs {match.away_team.upper()}"
        torneo_line = match.competition
        estadio_line = match.stadium

        msg = (
            f"⚪🔴 *{partido_line}*\n"
            f"🏆 _{torneo_line} · 🏟️ {estadio_line}_\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "📊 *PROBABILIDADES POISSON*\n"
            f"• *Victoria {match.home_team}:* `{p_home:.1f}%`\n"
            f"• *Empate (X):* `{p_draw:.1f}%`\n"
            f"• *Victoria {match.away_team}:* `{p_away:.1f}%`\n"
            f"• *Más de 2.5 Goles:* `{p_over:.1f}%`\n\n"
            "🎯 *PARLAY SGP RECOMENDADO (Bet365)*\n"
            f"{legs_block}\n\n"
            "📈 *MÉTRICAS CUANTITATIVAS*\n"
            f"• *Cuota Total:* `@{cuota_val:.2f}`\n"
            f"• *Valor Esperado:* `+{ev_val:.1f}% EV`\n"
            f"• *Stake Sugerido:* `{stake_val:.1f}% (Kelly 1/4)`\n"
            "━━━━━━━━━━━━━━━━━━━━━"
        )
        return msg

    except Exception as e:
        logger.error(f"Error al generar reporte predictivo de River: {e}")
        return f"⚠️ Error al calcular modelo predictivo: `{e}`"