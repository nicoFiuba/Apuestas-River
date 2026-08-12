"""
Cliente asíncrono de API para extracción de datos de partidos de fútbol y cuotas.

Utiliza Pydantic v2 para esquemas estrictos inmutables e httpx.AsyncClient 
para peticiones HTTP reactivas de alto rendimiento.
"""

from datetime import datetime, timezone
import logging
import httpx
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


class OddsSchema(BaseModel):
    """Esquema de cuotas 1X2 (Bet365 / Mercado principal)."""

    model_config = ConfigDict(frozen=True)

    home_win: float = Field(..., gt=1.0, description="Cuota para victoria local")
    draw: float = Field(..., gt=1.0, description="Cuota para empate")
    away_win: float = Field(..., gt=1.0, description="Cuota para victoria visitante")


class MatchSchema(BaseModel):
    """
    Modelo representativo inmutable de un partido de fútbol analizado por el motor.
    """

    model_config = ConfigDict(frozen=True)

    match_id: str = Field(..., description="Identificador único del encuentro")
    competition: str = Field(..., description="Torneo o competición")
    datetime_utc: datetime = Field(..., description="Fecha y hora oficial UTC")
    home_team: str = Field(..., description="Nombre del equipo local")
    away_team: str = Field(..., description="Nombre del equipo visitante")
    stadium: str = Field(..., description="Estadio del partido")
    status: str = Field(default="SCHEDULED", description="Estado del partido (SCHEDULED, FINISHED, LIVE)")
    home_score: int = Field(default=0, ge=0, description="Goles anotados por el local")
    away_score: int = Field(default=0, ge=0, description="Goles anotados por el visitante")
    possession_home: int = Field(default=50, ge=0, le=100, description="Porcentaje de posesión local")
    possession_away: int = Field(default=50, ge=0, le=100, description="Porcentaje de posesión visitante")
    corners_home: int = Field(default=0, ge=0, description="Tiros de esquina local")
    corners_away: int = Field(default=0, ge=0, description="Tiros de esquina visitante")
    odds: OddsSchema = Field(..., description="Cuotas registradas")
    is_ev_plus: bool = Field(default=False, description="Flag de Valor Esperado Positivo detectado por el modelo")
    ev_value: float = Field(default=0.00, description="Porcentaje o valor EV estimado")
    recommended_market: str | None = Field(default=None, description="Mercado sugerido para operar")


def _get_mock_river_matches() -> list[MatchSchema]:
    """
    Genera datos mock estructurados y validados de partidos de River Plate.

    Returns:
        list[MatchSchema]: Lista de objetos MatchSchema inmutables.
    """
    return [
        MatchSchema(
            match_id="RIV-2026-001",
            competition="Liga Profesional de Fútbol",
            datetime_utc=datetime(2026, 8, 12, 23, 30, tzinfo=timezone.utc),
            home_team="River Plate",
            away_team="Boca Juniors",
            stadium="MÁS Monumental",
            status="SCHEDULED",
            home_score=0,
            away_score=0,
            possession_home=55,
            possession_away=45,
            corners_home=6,
            corners_away=3,
            odds=OddsSchema(home_win=1.95, draw=3.40, away_win=4.20),
            is_ev_plus=True,
            ev_value=5.40,
            recommended_market="River Plate Gana Directo (Cuota 1.95 - EV+: +5.4%)",
        ),
        MatchSchema(
            match_id="RIV-2026-002",
            competition="Copa Libertadores",
            datetime_utc=datetime(2026, 8, 19, 21, 0, tzinfo=timezone.utc),
            home_team="Palmeiras",
            away_team="River Plate",
            stadium="Allianz Parque",
            status="SCHEDULED",
            home_score=0,
            away_score=0,
            possession_home=48,
            possession_away=52,
            corners_home=4,
            corners_away=5,
            odds=OddsSchema(home_win=2.20, draw=3.10, away_win=3.50),
            is_ev_plus=True,
            ev_value=3.80,
            recommended_market="Hándicap Asiático River Plate +0.5 (Cuota 1.80 - EV+: +3.8%)",
        ),
        MatchSchema(
            match_id="RIV-2026-003",
            competition="Liga Profesional de Fútbol",
            datetime_utc=datetime(2026, 8, 24, 20, 15, tzinfo=timezone.utc),
            home_team="River Plate",
            away_team="Independiente",
            stadium="MÁS Monumental",
            status="SCHEDULED",
            home_score=0,
            away_score=0,
            possession_home=60,
            possession_away=40,
            corners_home=7,
            corners_away=2,
            odds=OddsSchema(home_win=1.65, draw=3.80, away_win=5.50),
            is_ev_plus=False,
            ev_value=0.00,
            recommended_market=None,
        ),
    ]


async def fetch_river_matches(api_key: str) -> list[MatchSchema]:
    """
    Consulta asíncrona a la API de datos deportivos para obtener próximos encuentros de River Plate.

    Si la API real no está disponible o la key es de simulación mock,
    retorna automáticamente un conjunto de datos estructurados y validados con MatchSchema.

    Args:
        api_key (str): Clave de autenticación para la API.

    Returns:
        list[MatchSchema]: Lista de partidos validados.

    Raises:
        httpx.HTTPError: Si la API remota devuelve un error HTTP inesperado.
    """
    api_url = "https://api.football-data-provider.com/v1/teams/river-plate/matches"
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}

    if api_key.startswith("mock_") or "secret" in api_key:
        logger.info("Utilizando proveedor de datos mock local para partidos de River Plate.")
        return _get_mock_river_matches()

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            logger.info("Realizando petición HTTP GET asíncrona a %s", api_url)
            response = await client.get(api_url, headers=headers)
            response.raise_for_status()

            raw_data = response.json()
            matches = [MatchSchema(**item) for item in raw_data.get("matches", [])]
            logger.info("Se recuperaron exitosamente %d partidos desde la API.", len(matches))
            return matches

    except httpx.HTTPStatusError as exc:
        logger.error("Error de respuesta HTTP [%d] de la API: %s", exc.response.status_code, exc)
        raise
    except httpx.RequestError as exc:
        logger.warning("No se pudo contactar a la API remota (%s). Retornando fallback mock.", exc)
        return _get_mock_river_matches()
