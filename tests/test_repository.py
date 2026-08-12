"""
Pruebas unitarias para el Repositorio de Base de Datos y la Inicialización de Esquema.
"""

from unittest.mock import MagicMock, patch
from datetime import datetime, timezone
import pytest

from src.data.api_client import MatchSchema, OddsSchema
from src.db.repository import get_or_create_team, save_match_cascade, save_matches_bulk
from src.db.init_db import init_database


@pytest.fixture
def mock_match() -> MatchSchema:
    return MatchSchema(
        match_id="TEST-RIV-001",
        competition="Liga Profesional",
        datetime_utc=datetime(2026, 9, 1, 18, 0, tzinfo=timezone.utc),
        home_team="River Plate",
        away_team="Boca Juniors",
        stadium="MÁS Monumental",
        status="SCHEDULED",
        home_score=0,
        away_score=0,
        possession_home=55,
        possession_away=45,
        corners_home=5,
        corners_away=2,
        odds=OddsSchema(home_win=1.90, draw=3.20, away_win=4.00),
        is_ev_plus=True,
        ev_value=4.50,
        recommended_market="River Plate Gana",
    )


def test_get_or_create_team_existing() -> None:
    """Valida la obtención de un equipo existente."""
    cursor = MagicMock()
    cursor.fetchone.return_value = {"id": 10}

    team_id = get_or_create_team(cursor, "River Plate")
    assert team_id == 10
    cursor.execute.assert_called_once_with(
        "SELECT id FROM teams WHERE name = %s;", ("River Plate",)
    )


def test_get_or_create_team_new() -> None:
    """Valida la creación de un nuevo equipo cuando no existe en BD."""
    cursor = MagicMock()
    cursor.fetchone.return_value = None
    cursor.lastrowid = 25

    team_id = get_or_create_team(cursor, "Boca Juniors", "BOC")
    assert team_id == 25
    assert cursor.execute.call_count == 2


def test_save_match_cascade(mock_match: MatchSchema) -> None:
    """Valida que la persistencia en cascada ejecute todas las sentencias en el cursor."""
    cursor = MagicMock()
    cursor.fetchone.side_effect = [{"id": 1}, {"id": 2}]

    save_match_cascade(cursor, mock_match)
    
    # 2 SELECT + 1 INSERT matches + 1 INSERT scores + 1 INSERT stats + 1 INSERT odds = 6 consultas
    assert cursor.execute.call_count == 6


@patch("src.db.repository.get_db_connection")
def test_save_matches_bulk_success(mock_get_conn: MagicMock, mock_match: MatchSchema) -> None:
    """Valida la ejecución en lote dentro de una transacción atómica."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_conn.return_value.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_cursor.fetchone.side_effect = [{"id": 1}, {"id": 2}]

    result = save_matches_bulk([mock_match])
    assert result == 1
    mock_conn.commit.assert_called_once()


def test_init_database_missing_file() -> None:
    """Valida el manejo seguro si schema.sql no estuviera presente."""
    with patch("src.db.init_db.Path.exists", return_value=False):
        assert init_database() is False
