"""
Módulo de Inicialización del Esquema de Base de Datos MySQL.

Ejecuta las sentencias DDL definidas en `src/db/schema.sql` 
garantizando la existencia e integridad de las tablas e índices relacionales.
"""

import logging
from pathlib import Path
import pymysql

from src.db.connection import get_db_connection

logger = logging.getLogger(__name__)


def init_database() -> bool:
    """
    Lee e inicializa el esquema DDL de la base de datos desde `schema.sql`.

    Returns:
        bool: True si el esquema se aplicó correctamente, False si la BD no está disponible.
    """
    schema_file = Path(__file__).parent / "schema.sql"
    if not schema_file.exists():
        logger.error("Archivo DDL del esquema no encontrado en: %s", schema_file)
        return False

    try:
        with open(schema_file, "r", encoding="utf-8") as f:
            sql_content = f.read()

        # Dividir el script por punto y coma, ignorando comentarios y bloques vacíos
        statements = [
            stmt.strip()
            for stmt in sql_content.split(";")
            if stmt.strip() and not stmt.strip().startswith("--")
        ]

        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                for statement in statements:
                    if statement:
                        cursor.execute(statement)
                        conn.commit()
            logger.info(
                "Esquema DDL de base de datos MySQL verificado/inicializado (%d sentencias ejecutadas).",
                len(statements),
            )
            return True

    except pymysql.MySQLError as exc:
        logger.warning("No se pudo inicializar el esquema en MySQL: %s", exc)
        return False
    except Exception as exc:
        logger.error("Error al leer o ejecutar schema.sql: %s", exc)
        return False
