from fastapi import APIRouter, HTTPException, Query
from services.scoring import (
    fetch_all_season_stats,
    fetch_all_10day_stats,
    fetch_todays_games,
    fetch_splits,
    fetch_h2h,
    fetch_team_map,
    score_player,
)
from services.weather import get_weather_for_venue
from routers.scores import build_shared_data
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

router = APIRouter()

MAX_SEARCH_RESULTS = 10


def _team_names() -> dict:
    """Resolve team names from today's games, falling back to the
    league-wide team list (both cached)."""
    names = {}
    try:
        for game in fetch_todays_games():
            names[game["home_team_id"]] = game["home_team_name"]
            names[game["away_team_id"]] = game["away_team_name"]
    except Exception:
        pass
    try:
        for team_id, name in fetch_team_map().items():
            names.setdefault(team_id, name)
    except Exception:
        pass
    return names


def _todays_matchup_for_team(team_id: int) -> dict | None:
    """Find today's game info for a team, including the opposing
    probable pitcher. Returns None if the team isn't playing today."""
    try:
        games = fetch_todays_games()
    except Exception:
        return None

    for game in games:
        if game["home_team_id"] == team_id:
            side, opp_pitcher = "home", game.get("away_probable_pitcher")
            opp_id, opp_name = game["away_team_id"], game["away_team_name"]
        elif game["away_team_id"] == team_id:
            side, opp_pitcher = "away", game.get("home_probable_pitcher")
            opp_id, opp_name = game["home_team_id"], game["home_team_name"]
        else:
            continue

        return {
            "side": side,
            "venue": game["venue"],
            "opp_team_id": opp_id,
            "opp_team_name": opp_name,
            "opp_pitcher": opp_pitcher,
        }
    return None


def build_player_card(player: dict, shared: dict) -> dict:
    """
    Assemble a player card: identity, season line, last-10-day form,
    L/R splits, and — when the player's team has a game today with a
    probable opposing pitcher — today's matchup and model score.
    """
    year = datetime.now().year
    pid = player["player_id"]
    team_id = player["team_id"]

    card = {
        "player_id": pid,
        "name": player["name"],
        "team_id": team_id,
        "team_name": _team_names().get(team_id, "Unknown"),
        "bats": player.get("bats", "R"),
        "season": {
            "avg": player["avg"],
            "ops": player["ops"],
            "hr": player["hr"],
            "pa": player["pa"],
        },
        "last_10": None,
        "splits": None,
        "today": None,
    }

    ten_day = next(
        (p for p in shared["all_10day"] if p["player_id"] == pid), None
    )
    if ten_day:
        card["last_10"] = {
            "avg": ten_day["avg"],
            "ops": ten_day["ops"],
            "pa": ten_day.get("pa"),
        }

    try:
        card["splits"] = fetch_splits(pid, year)
    except Exception:
        card["splits"] = None

    matchup = _todays_matchup_for_team(team_id)
    if matchup and matchup["opp_pitcher"]:
        pitcher = matchup["opp_pitcher"]
        pitcher_id = pitcher["id"]
        pitcher_hand = pitcher.get("pitchHand", {}).get("code", "R")

        batter_hand = player.get("bats", "R")
        if batter_hand == "S":
            batter_hand = "L" if pitcher_hand == "R" else "R"

        try:
            weather = get_weather_for_venue(matchup["venue"])
            h2h = fetch_h2h(pid, pitcher_id)
            result = score_player(
                player_id=pid,
                venue=matchup["venue"],
                batter_hand=batter_hand,
                pitcher_id=pitcher_id,
                pitcher_hand=pitcher_hand,
                opp_team_id=matchup["opp_team_id"],
                weather=weather,
                h2h=h2h,
                **shared,
            )
            card["today"] = {
                "opponent": matchup["opp_team_name"],
                "venue": matchup["venue"],
                "side": matchup["side"],
                "pitcher": {
                    "id": pitcher_id,
                    "name": pitcher.get("fullName"),
                    "hand": pitcher_hand,
                },
                "total_score": result["total_score"],
                "core_score": result["core_score"],
                "bonus_score": result["bonus_score"],
                "breakdown": result["breakdown"],
                "h2h": h2h,
                "h2h_note": result["h2h_note"],
            }
        except Exception:
            card["today"] = None

    return card


@router.get("/players/search")
def search_players(q: str = Query("", description="Player name query")):
    """
    Search projected hitters by name (case-insensitive substring).
    Returns full player cards, including today's score when available.
    """
    try:
        query = q.strip().lower()
        if len(query) < 2:
            return {"query": q, "count": 0, "players": []}

        year = datetime.now().year
        all_season = fetch_all_season_stats(year)
        matches = [
            p for p in all_season if query in p["name"].lower()
        ][:MAX_SEARCH_RESULTS]

        if not matches:
            return {"query": q, "count": 0, "players": []}

        shared = build_shared_data(year)

        with ThreadPoolExecutor(max_workers=5) as executor:
            cards = list(executor.map(
                lambda p: build_player_card(p, shared), matches
            ))

        return {"query": q, "count": len(cards), "players": cards}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/players/{player_id}")
def get_player(player_id: int):
    """Full card for a single player (used by the frontend metric panels)."""
    try:
        year = datetime.now().year
        all_season = fetch_all_season_stats(year)
        player = next(
            (p for p in all_season if p["player_id"] == player_id), None
        )
        if not player:
            raise HTTPException(
                status_code=404, detail="Player not found"
            )

        shared = build_shared_data(year)
        return build_player_card(player, shared)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
