"""
Módulo de Repositorio de Datos (Repository Pattern).

Proporciona funciones atómicas y transaccionales para la persistencia
y actualización en cascada de entidades en MySQL (`teams`, `matches`, `match_scores`, `match_stats`, `odds_and_ev`).
"""

import logging
from typing import Any

import pymysql

from src.data.api_client import MatchSchema
from src.db.connection import get_db_connection

logger = logging.getLogger(__name__)


def get_or_create_team(cursor: Any, team_name: str, short_code: str | None = None) -> int:
    """
    Busca un equipo por nombre. Si no existe, lo inserta y retorna su ID primario.

    Args:
        cursor: Cursor activo de la conexión MySQL.
        team_name (str): Nombre del equipo.
        short_code (str | None): Código corto opcional (ej: 'RIV', 'BOC').

    Returns:
        int: ID primario del equipo en la tabla `teams`.
    """
    cursor.execute("SELECT id FROM teams WHERE name = %s;", (team_name,))
    row = cursor.fetchone()
    if row:
        return int(row["id"] if isinstance(row, dict) else row[0])

    if not short_code:
        short_code = team_name[:3].upper()

    cursor.execute(
        "INSERT INTO teams (name, short_code) VALUES (%s, %s);",
        (team_name, short_code),
    )
    return int(cursor.lastrowid)


def save_match_cascade(cursor: Any, match: MatchSchema) -> None:
    """
    Inserta o actualiza un partido y todas sus entidades asociadas en cascada atómica.

    Utiliza sintaxis `ON DUPLICATE KEY UPDATE` para garantizar idempotencia.

    Args:
        cursor: Cursor activo de la conexión MySQL.
        match (MatchSchema): Instancia inmutable con la información completa del partido.
    """
    # 1. Obtener/Crear Equipos
    home_team_id = get_or_create_team(cursor, match.home_team)
    away_team_id = get_or_create_team(cursor, match.away_team)

    # 2. Insertar / Actualizar Partido Principal
    query_matches = """
        INSERT INTO matches (id, competition, match_date, home_team_id, away_team_id, stadium, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            competition = VALUES(competition),
            match_date = VALUES(match_date),
            home_team_id = VALUES(home_team_id),
            away_team_id = VALUES(away_team_id),
            stadium = VALUES(stadium),
            status = VALUES(status);
    """
    cursor.execute(
        query_matches,
        (
            match.match_id,
            match.competition,
            match.datetime_utc.strftime("%Y-%m-%d %H:%M:%S"),
            home_team_id,
            away_team_id,
            match.stadium,
            match.status,
        ),
    )

    # 3. Insertar / Actualizar Marcadores
    query_scores = """
        INSERT INTO match_scores (match_id, home_score, away_score)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE
            home_score = VALUES(home_score),
            away_score = VALUES(away_score);
    """
    cursor.execute(query_scores, (match.match_id, match.home_score, match.away_score))

    # 4. Insertar / Actualizar Estadísticas Avanzadas
    query_stats = """
        INSERT INTO match_stats (match_id, possession_home, possession_away, corners_home, corners_away)
        VALUES (%s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            possession_home = VALUES(possession_home),
            possession_away = VALUES(possession_away),
            corners_home = VALUES(corners_home),
            corners_away = VALUES(corners_away);
    """
    cursor.execute(
        query_stats,
        (
            match.match_id,
            match.possession_home,
            match.possession_away,
            match.corners_home,
            match.corners_away,
        ),
    )

    # 5. Registrar Histórico de Cuotas y EV+
    query_odds = """
        INSERT INTO odds_and_ev (match_id, odds_home, odds_draw, odds_away, ev_value, recommended_bet)
        VALUES (%s, %s, %s, %s, %s, %s);
    """
    cursor.execute(
        query_odds,
        (
            match.match_id,
            match.odds.home_win,
            match.odds.draw,
            match.odds.away_win,
            match.ev_value,
            match.recommended_market,
        ),
    )


def save_matches_bulk(matches: list[MatchSchema]) -> int:
    """
    Guarda una lista de partidos en la base de datos dentro de una transacción atómica.

    Args:
        matches (list[MatchSchema]): Lista de partidos validados.

    Returns:
        int: Cantidad de partidos persistidos con éxito.
    """
    if not matches:
        return 0

    saved_count = 0
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                for match in matches:
                    save_match_cascade(cursor, match)
                    saved_count += 1
                conn.commit()
            logger.info("Transacción atómica completada: %d partidos persistidos en MySQL.", saved_count)
            return saved_count
    except pymysql.MySQLError as exc:
        logger.error("Error en la transacción de persistencia MySQL: %s. Realizando rollback.", exc)
        return 0
    except Exception as exc:
        logger.error("Error inesperado durante la persistencia de partidos: %s", exc)
        return 0
