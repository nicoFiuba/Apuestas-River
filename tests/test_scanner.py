"""
Pruebas unitarias para los módulos de Escaneo en Tiempo Real, Alertas y Odds Client.
"""

from unittest.mock import patch
import pytest

from src.analytics.ev_calculator import evaluate_bet
from src.analytics.parlay_builder import build_same_game_parlay
from src.data.odds_client import LiveBookmakerOdds, fetch_live_market_odds
from src.notifications.alert_service import dispatch_alert, format_alert_message
from src.services.scanner_service import scan_river_value_bets


@pytest.mark.asyncio
async def test_fetch_live_market_odds() -> None:
    """Valida la obtención asíncrona de cuotas vivas en formato Pydantic v2."""
    odds_list = await fetch_live_market_odds(api_key="mock_api_key")
    assert isinstance(odds_list, list)
    assert len(odds_list) > 0
    assert isinstance(odds_list[0], LiveBookmakerOdds)
    assert odds_list[0].bookmaker == "Bet365"
    assert odds_list[0].odds_1x2.home_win > 1.0


def test_format_alert_message() -> None:
    """Valida que la plantilla de alerta genere el formato Markdown con emojis."""
    rec1 = evaluate_bet("Victoria Local (River Plate)", real_prob=0.66, odds=1.95)
    parlay = build_same_game_parlay("RIV-001", [rec1, evaluate_bet("Over 2.5", 0.56, 1.92)])

    alert_text = format_alert_message("River Plate vs Boca Juniors", [rec1], parlay)

    assert "ALERTA DE APUESTA CON VALOR (+EV) DETECTADA" in alert_text
    assert "River Plate vs Boca Juniors" in alert_text
    assert "+EV" in alert_text
    assert "Bet365" in alert_text


@pytest.mark.asyncio
async def test_dispatch_alert_console_mode() -> None:
    """Valida que el despacho de alerta funcione correctamente en modo consola."""
    rec1 = evaluate_bet("Victoria Local (River Plate)", real_prob=0.66, odds=1.95)
    sent = await dispatch_alert("River Plate vs Boca Juniors", [rec1], None)
    assert sent is True


@pytest.mark.asyncio
async def test_scan_river_value_bets_pipeline() -> None:
    """Valida la ejecución del servicio escáner de punta a punta."""
    with patch("src.services.scanner_service.test_connection", return_value=False):
        result = await scan_river_value_bets(min_ev_threshold=3.5, send_alerts=False, save_to_db=False)

    assert result["status"] == "SUCCESS"
    assert result["matches_scanned"] == 3
    assert result["total_ev_bets"] > 0
