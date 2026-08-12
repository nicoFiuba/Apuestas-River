"""
Punto de Entrada Principal (Main Script) - Sprint 4: Orquestación Final y Menú Interactivo.

Ofrece un menú asíncrono interactivo para ejecutar:
1. Escaneo en tiempo real de apuestas EV+ (> +3.5%) y Same Game Parlays (Bet365 x3.00+).
2. Persistencia atómica de predicciones en MySQL.
3. Despacho automatizado de Alertas a Telegram Bot API / Consola.
4. Ejecución del Pipeline Automatizado Completo.
"""

import asyncio
import logging
import sys

from src.data.api_client import fetch_river_matches
from src.db.connection import test_connection
from src.db.init_db import init_database
from src.db.repository import save_matches_bulk
from src.notifications.alert_service import dispatch_alert
from src.services.engine_service import run_predictive_analysis
from src.services.scanner_service import scan_river_value_bets
from src.utils.config import settings

# Configurar soporte UTF-8 para consolas Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger("RiverBettingEngine")


async def option_run_scan() -> None:
    """Opción 1: Ejecutar escaneo de cuotas EV+ y mostrar reporte."""
    logger.info("Ejecutando escaneo cuantitativo en tiempo real...")
    res = await scan_river_value_bets(min_ev_threshold=3.5, send_alerts=False, save_to_db=False)
    print(f"\n✅ Escaneo completado: {res['matches_scanned']} partidos analizados | {res['total_ev_bets']} apuestas EV+ encontradas.")


async def option_save_to_db() -> None:
    """Opción 2: Guardar predicciones e historial en MySQL."""
    logger.info("Inicializando persistencia en MySQL...")
    if not test_connection():
        print("\n❌ Error: No se puede conectar a la base de datos MySQL local (port 3306).")
        return

    init_database()
    matches = await fetch_river_matches(settings.api_key)
    saved = save_matches_bulk(matches)
    print(f"\n✅ Operación completada: {saved} / {len(matches)} partidos guardados atómicamente en MySQL.")


async def option_send_alerts() -> None:
    """Opción 3: Despachar alertas automáticas a Telegram Bot API / Consola."""
    logger.info("Procesando y despachando alertas automatizadas...")
    matches = await fetch_river_matches(settings.api_key)
    reports = run_predictive_analysis(matches)

    alerts_sent = 0
    for rep in reports:
        sent = await dispatch_alert(
            match_teams=rep["teams"],
            ev_bets=rep["ev_plus_bets"],
            parlay=rep["same_game_parlay"],
        )
        if sent:
            alerts_sent += 1

    print(f"\n✅ Sistema de alertas procesado: {alerts_sent} alertas despachadas.")


async def option_run_full_pipeline() -> None:
    """Opción 4: Ejecutar pipeline completo automatizado."""
    logger.info("Ejecutando Pipeline Automatizado Completo (Escaneo + Persistencia + Alertas)...")
    res = await scan_river_value_bets(min_ev_threshold=3.5, send_alerts=True, save_to_db=True)
    print("\n======================================================================")
    print(" 🎉 PIPELINE AUTOMATIZADO COMPLETADO CON ÉXITO")
    print(f" -> Partidos Escaneados: {res['matches_scanned']}")
    print(f" -> Persistidos en MySQL: {res['db_persisted']}")
    print(f" -> Apuestas EV+ Detectadas: {res['total_ev_bets']}")
    print(f" -> Alertas Despachadas: {res['alerts_sent']}")
    print("======================================================================\n")


async def main() -> None:
    """Orquestador principal con ejecución directa del pipeline completo o menú."""
    print("\n" + "=" * 70)
    print(" ⚽ MOTOR PREDICTIVO DE APUESTAS EV+ - RIVER PLATE (Sprint 4)")
    print("======================================================================")

    # Si se ejecuta sin parámetros interactivos o en script automático, corre el pipeline completo
    if len(sys.argv) > 1 and sys.argv[1] == "--menu":
        while True:
            print("\n📋 MENÚ DE OPCIONES DEL SISTEMA:")
            print(" 1. Ejecutar escaneo en tiempo real e imprimir apuestas EV+")
            print(" 2. Guardar predicciones e historial en MySQL")
            print(" 3. Enviar alertas automáticas (Telegram API / Consola)")
            print(" 4. Ejecutar Pipeline Automatizado Completo")
            print(" 5. Salir")

            try:
                choice = input("\nSeleccione una opción (1-5): ").strip()
            except EOFError:
                choice = "4"

            if choice == "1":
                await option_run_scan()
            elif choice == "2":
                await option_save_to_db()
            elif choice == "3":
                await option_send_alerts()
            elif choice == "4":
                await option_run_full_pipeline()
            elif choice == "5":
                print("\n¡Gracias por utilizar el Motor Predictivo de Apuestas - River Plate!\n")
                break
            else:
                print("Opción inválida. Intente de nuevo.")
    else:
        # Modo por defecto: Ejecuta el pipeline completo de punta a punta
        await option_run_full_pipeline()


if __name__ == "__main__":
    asyncio.run(main())
