from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import auth, leaders, players, scores, teams, validation
from contextlib import asynccontextmanager
from services.scoring import (
    fetch_all_season_stats,
    fetch_all_10day_stats,
    fetch_bullpen_eras,
    fetch_todays_games,
    fetch_todays_lineups,
    fetch_splits,
    get_statcast_batter_cached,
    load_cache_from_disk,
    save_cache_to_disk,
)
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import threading
from dotenv import load_dotenv
load_dotenv()


def warm_caches():
    """
    Pre-fetch the league-wide data and per-player Statcast/splits data
    for everyone in today's games, so the first /api/scores/today call
    doesn't pay the full fetch cost.
    Runs in a background thread on server startup.
    """
    try:
        print("Warming shared data caches...")
        year = datetime.now().year
        all_season = fetch_all_season_stats(year)
        fetch_all_10day_stats(year)
        fetch_bullpen_eras(year)
        games = fetch_todays_games()
        fetch_todays_lineups()

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

        print(
            f"Pre-fetching Statcast + splits for "
            f"{len(todays_players)} players..."
        )

        def fetch_one(player):
            try:
                get_statcast_batter_cached(
                    player["player_id"], persist=False
                )
            except Exception as e:
                print(f"Cache warm failed for {player['name']}: {e}")
            try:
                fetch_splits(player["player_id"], year)
            except Exception:
                pass

        # Fetch concurrently with limited workers to avoid
        # overwhelming Baseball Savant
        with ThreadPoolExecutor(max_workers=5) as executor:
            executor.map(fetch_one, todays_players)

        # Persist the Statcast cache once, after the batch completes
        save_cache_to_disk()
        print("Caches warmed successfully.")

    except Exception as e:
        print(f"Cache warming failed: {e}")


@asynccontextmanager
async def lifespan(app):
    # Reuse any Statcast data persisted by a previous run
    load_cache_from_disk()
    # Run cache warming in background so server starts immediately
    thread = threading.Thread(target=warm_caches, daemon=True)
    thread.start()
    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(leaders.router, prefix="/api")
app.include_router(scores.router, prefix="/api")
app.include_router(players.router, prefix="/api")
app.include_router(teams.router, prefix="/api")
app.include_router(validation.router, prefix="/api")

@app.get("/")
def root():
    return {"message": "Analytic Overview API is running"}
