import os
import httpx
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Ubicar la raíz del proyecto y cargar .env de forma explícita
BASE_DIR = Path(__file__).resolve().parent.parent.parent
dotenv_path = BASE_DIR / ".env"
load_dotenv(dotenv_path=dotenv_path)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


class BookmakerOdds(BaseModel):
    bookmaker: str
    home_win: float
    draw: float
    away_win: float


class RealMatchOdds(BaseModel):
    match_id: str
    sport_key: str
    home_team: str
    away_team: str
    commence_time: str
    bookmakers: list[BookmakerOdds] = Field(default_factory=list)


async def fetch_real_soccer_odds() -> list[RealMatchOdds]:
    api_key = os.getenv("ODDS_API_KEY")
    if not api_key:
        logging.error(f"No se encontró la ODDS_API_KEY en el archivo .env ({dotenv_path})")
        return []

    url = "https://api.the-odds-api.com/v4/sports/soccer_argentina_primera_division/odds/"
    params = {
        "apiKey": api_key,
        "regions": "us,uk,eu,au",
        "markets": "h2h",
        "dateFormat": "iso"
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

        matches_odds = []
        for item in data:
            match_id = item.get("id")
            sport_key = item.get("sport_key")
            home_team = item.get("home_team")
            away_team = item.get("away_team")
            commence_time = item.get("commence_time")

            bookmakers_list = []
            for bm in item.get("bookmakers", []):
                bm_title = bm.get("title")
                markets = bm.get("markets", [])
                
                if markets:
                    outcomes = markets[0].get("outcomes", [])
                    home_win, draw, away_win = 0.0, 0.0, 0.0
                    
                    for outcome in outcomes:
                        name = outcome.get("name")
                        price = outcome.get("price", 0.0)
                        if name == home_team:
                            home_win = price
                        elif name == away_team:
                            away_win = price
                        elif name == "Draw":
                            draw = price
                    
                    if home_win > 0 and away_win > 0:
                        bookmakers_list.append(
                            BookmakerOdds(
                                bookmaker=bm_title,
                                home_win=home_win,
                                draw=draw,
                                away_win=away_win
                            )
                        )

            matches_odds.append(
                RealMatchOdds(
                    match_id=match_id,
                    sport_key=sport_key,
                    home_team=home_team,
                    away_team=away_team,
                    commence_time=commence_time,
                    bookmakers=bookmakers_list
                )
            )

        logging.info(f"Éxito: Se obtuvieron {len(matches_odds)} partidos reales desde The Odds API.")
        return matches_odds

    except Exception as e:
        logging.error(f"Error al conectar con The Odds API: {e}")
        return []
