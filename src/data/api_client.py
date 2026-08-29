"""
Cliente de datos de partidos de fútbol y cuotas para River Plate.
"""

from datetime import datetime, timezone
import logging
import httpx
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


class OddsSchema(BaseModel):
    """Esquema de cuotas 1X2."""
    model_config = ConfigDict(frozen=True)

    home_win: float = Field(..., gt=1.0, description="Cuota para victoria local")
    draw: float = Field(..., gt=1.0, description="Cuota para empate")
    away_win: float = Field(..., gt=1.0, description="Cuota para victoria visitante")


class MatchSchema(BaseModel):
    """Modelo inmutable de un partido analizado."""
    model_config = ConfigDict(frozen=True)

    match_id: str = Field(..., description="Identificador único")
    competition: str = Field(..., description="Torneo")
    datetime_utc: datetime = Field(..., description="Fecha UTC")
    home_team: str = Field(..., description="Equipo local")
    away_team: str = Field(..., description="Equipo visitante")
    stadium: str = Field(..., description="Estadio")
    status: str = Field(default="SCHEDULED")
    home_score: int = Field(default=0, ge=0)
    away_score: int = Field(default=0, ge=0)
    possession_home: int = Field(default=50, ge=0, le=100)
    possession_away: int = Field(default=50, ge=0, le=100)
    corners_home: int = Field(default=0, ge=0)
    corners_away: int = Field(default=0, ge=0)
    odds: OddsSchema = Field(...)
    is_ev_plus: bool = Field(default=False)
    ev_value: float = Field(default=0.00)
    recommended_market: str | None = Field(default=None)


def _get_mock_river_matches() -> list[MatchSchema]:
    """Retorna el fixture actualizado de River Plate."""
    return [
        MatchSchema(
            match_id="RIV-2026-001",
            competition="Torneo Clausura",
            datetime_utc=datetime(2026, 8, 30, 18, 0, tzinfo=timezone.utc),
            home_team="Banfield",
            away_team="River Plate",
            stadium="Estadio Florencio Sola",
            status="SCHEDULED",
            home_score=0,
            away_score=0,
            possession_home=42,
            possession_away=58,
            corners_home=3,
            corners_away=6,
            odds=OddsSchema(home_win=4.10, draw=3.30, away_win=1.92),
            is_ev_plus=True,
            ev_value=6.80,
            recommended_market="Victoria River Plate & +1.5 goles",
        ),
        MatchSchema(
            match_id="RIV-2026-002",
            competition="Copa Libertadores",
            datetime_utc=datetime(2026, 9, 10, 21, 30, tzinfo=timezone.utc),
            home_team="Palmeiras",
            away_team="River Plate",
            stadium="Allianz Parque",
            status="SCHEDULED",
            home_score=0,
            away_score=0,
            possession_home=50,
            possession_away=50,
            corners_home=4,
            corners_away=5,
            odds=OddsSchema(home_win=2.20, draw=3.10, away_win=3.50),
            is_ev_plus=True,
            ev_value=3.80,
            recommended_market="Hándicap Asiático River Plate +0.5",
        ),
    ]


async def fetch_river_matches(api_key: str = "") -> list[MatchSchema]:
    return _get_mock_river_matches()
