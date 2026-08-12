"""
Módulo de conexión y gestión de la base de datos MySQL.

Implementa un administrador de contexto fuertemente tipado consumiendo
la configuración inmutable del sistema y manejo explícito de excepciones.
"""

import logging
from collections.abc import Generator
from contextlib import contextmanager

import pymysql
from pymysql.connections import Connection

from src.utils.config import settings

logger = logging.getLogger(__name__)


@contextmanager
def get_db_connection() -> Generator[Connection, None, None]:
    """
    Administrador de contexto fuertemente tipado para manejar conexiones a MySQL.

    Garantiza el cierre automático de la conexión y el manejo de recursos.
    Yields:
        pymysql.connections.Connection: Objeto de conexión a MySQL.
    
    Raises:
        pymysql.MySQLError: Si ocurre un error durante la apertura o ejecución.
    """
    connection: Connection | None = None
    try:
        connection = pymysql.connect(
            host=settings.db_host,
            port=settings.db_port,
            user=settings.db_user,
            password=settings.db_password,
            database=settings.db_name,
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=3,
        )
        logger.info("Conexión a MySQL establecida correctamente (%s:%d)", settings.db_host, settings.db_port)
        yield connection
    except pymysql.MySQLError as exc:
        logger.error("Error grave en la conexión a la base de datos MySQL: %s", exc)
        raise
    finally:
        if connection and connection.open:
            connection.close()
            logger.debug("Conexión a MySQL cerrada adecuadamente.")


def test_connection() -> bool:
    """
    Verifica la salud de la conexión a la base de datos ejecutando 'SELECT 1;'.

    Returns:
        bool: True si la consulta responde exitosamente, False en caso de falla o inalcanzabilidad.
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1 AS alive;")
                result = cursor.fetchone()
                logger.info("Verificación SELECT 1 exitosa: %s", result)
                return True
    except pymysql.MySQLError as exc:
        logger.warning("Falla en prueba de conexión a MySQL (%s:%d): %s", settings.db_host, settings.db_port, exc)
        return False
