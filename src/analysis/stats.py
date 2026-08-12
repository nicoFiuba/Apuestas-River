import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Promedios base de la Liga Profesional Argentina
LEAGUE_AVG_HOME_GOALS = 1.32
LEAGUE_AVG_AWAY_GOALS = 1.05

# Datos de muestra de rendimiento reciente (Últimos partidos en LPF)
# En un entorno de producción avanzado, estos datos se pueden sincronizar vía Scraping/API deportiva.
TEAM_STATS_DATABASE = {
    "River Plate": {
        "home_goals_scored": 2.10,
        "home_goals_conceded": 0.70,
        "away_goals_scored": 1.50,
        "away_goals_conceded": 0.90,
    },
    "Argentinos Juniors": {
        "home_goals_scored": 1.20,
        "home_goals_conceded": 0.90,
        "away_goals_scored": 0.85,
        "away_goals_conceded": 1.40,
    },
    "Boca Juniors": {
        "home_goals_scored": 1.40,
        "home_goals_conceded": 0.80,
        "away_goals_scored": 1.00,
        "away_goals_conceded": 1.20,
    },
    "Racing Club": {
        "home_goals_scored": 1.60,
        "home_goals_conceded": 1.00,
        "away_goals_scored": 1.10,
        "away_goals_conceded": 1.30,
    },
    "Independiente": {
        "home_goals_scored": 1.10,
        "home_goals_conceded": 0.85,
        "away_goals_scored": 0.80,
        "away_goals_conceded": 1.10,
    },
    "San Lorenzo": {
        "home_goals_scored": 1.00,
        "home_goals_conceded": 0.75,
        "away_goals_scored": 0.70,
        "away_goals_conceded": 1.00,
    }
}


def get_team_poisson_ratings(home_team: str, away_team: str) -> dict:
    """
    Calcula los coeficientes de ataque y defensa para el Modelo de Poisson
    en base a las estadísticas reales recientes de los dos equipos.
    """
    # Valores por defecto en caso de no contar con el equipo específico en la BD
    default_home = {"home_goals_scored": 1.35, "home_goals_conceded": 1.10}
    default_away = {"away_goals_scored": 0.95, "away_goals_conceded": 1.35}

    home_data = TEAM_STATS_DATABASE.get(home_team, default_home)
    away_data = TEAM_STATS_DATABASE.get(away_team, default_away)

    # Coeficientes de Ataque y Defensa respecto al promedio de la liga
    home_attack = home_data.get("home_goals_scored", 1.35) / LEAGUE_AVG_HOME_GOALS
    home_defense = home_data.get("home_goals_conceded", 1.10) / LEAGUE_AVG_AWAY_GOALS

    away_attack = away_data.get("away_goals_scored", 0.95) / LEAGUE_AVG_AWAY_GOALS
    away_defense = away_data.get("away_goals_conceded", 1.35) / LEAGUE_AVG_HOME_GOALS

    return {
        "home_attack": round(home_attack, 2),
        "home_defense": round(home_defense, 2),
        "away_attack": round(away_attack, 2),
        "away_defense": round(away_defense, 2),
        "league_avg_home_goals": LEAGUE_AVG_HOME_GOALS,
        "league_avg_away_goals": LEAGUE_AVG_AWAY_GOALS
    }


if __name__ == "__main__":
    ratings = get_team_poisson_ratings("River Plate", "Argentinos Juniors")
    logging.info(f"Coeficientes calculados para River vs Argentinos: {ratings}")
