"""
Pruebas de validación iniciales para el Sprint 1.
"""

import pytest
from src.utils.config import settings
from src.data.api_client import fetch_river_matches, MatchSchema


def test_config_loaded() -> None:
    """Verifica que la configuración global inmutable se cargue correctamente."""
    assert settings.api_key is not None
    assert settings.db_port == 3306
    
    # Probar inmutabilidad de pydantic settings
    with pytest.raises(Exception):
        settings.db_port = 5432  # type: ignore[misc]


@pytest.mark.asyncio
async def test_fetch_river_matches_mock() -> None:
    """Verifica que la llamada asíncrona a la API retorne una lista de MatchSchema."""
    matches = await fetch_river_matches(settings.api_key)
    assert isinstance(matches, list)
    assert len(matches) > 0
    assert isinstance(matches[0], MatchSchema)
    assert "River" in matches[0].home_team or "River" in matches[0].away_team
