import requests
import pandas as pd
from datetime import datetime


MLB_API_BASE = "https://statsapi.mlb.com/api/v1"


def get_season_batting_stats():
    current_year = datetime.now().year

    # Fetch all hitters with at least 50 plate appearances this season
    url = f"{MLB_API_BASE}/stats"
    params = {
        "stats": "season",
        "group": "hitting",
        "season": current_year,
        "playerPool": "ALL",
        "limit": 300,
        "offset": 0,
        "sportId": 1,
        "sortStat": "homeRuns",
        "order": "desc",
    }

    response = requests.get(url, params=params)
    response.raise_for_status()
    data = response.json()

    players = []
    for entry in data["stats"][0]["splits"]:
        stat = entry["stat"]
        player = entry["player"]
        team = entry.get("team", {})

        # Skip players with very few plate appearances
        plate_appearances = stat.get("plateAppearances", 0)
        if plate_appearances < 50:
            continue

        avg = float(stat.get("avg", 0) or 0)
        ops = float(stat.get("ops", 0) or 0)
        hr = int(stat.get("homeRuns", 0) or 0)

        players.append({
            "name": player["fullName"],
            "team": team.get("abbreviation") or team.get("name", "N/A"),
            "player_id": player["id"],
            "hr": hr,
            "avg": avg,
            "ops": ops,
            "plate_appearances": plate_appearances,
        })

    return pd.DataFrame(players)


def get_leaders(days: int = 7):
    df = get_season_batting_stats()

    if df.empty:
        return {}

    hr_leader = df.loc[df["hr"].idxmax()]
    avg_leader = df.loc[df["avg"].idxmax()]
    ops_leader = df.loc[df["ops"].idxmax()]

    return {
        "hr_leader": format_player(hr_leader, "hr"),
        "avg_leader": format_player(avg_leader, "avg"),
        "ops_leader": format_player(ops_leader, "ops"),
    }


def format_player(row, featured_stat: str):
    return {
        "name": row["name"],
        "team": row["team"],
        "player_id": int(row["player_id"]),
        "stats": {
            "hr": int(row["hr"]),
            "avg": round(float(row["avg"]), 3),
            "ops": round(float(row["ops"]), 3),
        },
        "featured_stat": featured_stat,
    }