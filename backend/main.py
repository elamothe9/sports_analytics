from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import leaders, scores, validation
from contextlib import asynccontextmanager
from services.scoring import (
    fetch_all_season_stats,
    fetch_todays_games,
    get_statcast_batter_cached,
)
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import threading
from dotenv import load_dotenv
load_dotenv()


def warm_h2h_cache():
    """
    Pre-fetch Statcast data for all batters in today's games.
    Runs in a background thread on server startup.
    """
    try:
        print("Warming H2H cache for today's players...")
        year = datetime.now().year
        all_season = fetch_all_season_stats(year)
        games = fetch_todays_games()

        # Get all unique team IDs playing today
        todays_team_ids = set()
        for game in games:
            todays_team_ids.add(game["home_team_id"])
            todays_team_ids.add(game["away_team_id"])

        # Filter season players to only those playing today
        todays_players = [
            p for p in all_season
            if p["team_id"] in todays_team_ids
        ]

        print(f"Pre-fetching Statcast for {len(todays_players)} players...")

        def fetch_one(player):
            try:
                get_statcast_batter_cached(player["player_id"])
            except Exception as e:
                print(f"Cache warm failed for {player['name']}: {e}")

        # Fetch concurrently with limited workers to avoid
        # overwhelming Baseball Savant
        with ThreadPoolExecutor(max_workers=5) as executor:
            executor.map(fetch_one, todays_players)

        print("H2H cache warmed successfully.")

    except Exception as e:
        print(f"Cache warming failed: {e}")


@asynccontextmanager
async def lifespan(app):
    # Run cache warming in background so server starts immediately
    thread = threading.Thread(target=warm_h2h_cache, daemon=True)
    thread.start()
    yield


app = FastAPI(lifespan=lifespan)
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(leaders.router, prefix="/api")
app.include_router(scores.router, prefix="/api")
app.include_router(validation.router, prefix="/api")

@app.get("/")
def root():
    return {"message": "Analytic Overview API is running"}