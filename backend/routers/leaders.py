from pybaseball import batting_stats
import pandas as pd
from datetime import datetime, timedelta


def get_leaders(days: int = 7):
    current_year = datetime.now().year

    # Pull season stats — pybaseball doesn't support date ranges for
    # aggregate stats so we use Statcast per-player data instead
    df = batting_stats(current_year, qual=50)

    # Rename columns for easier access
    df = df.rename(columns={
        "Name": "name",
        "Team": "team",
        "HR": "hr",
        "AVG": "avg",
        "OPS": "ops",
        "playerid": "player_id",
    })

    # Drop rows missing key stats
    df = df.dropna(subset=["hr", "avg", "ops"])

    # Get leaders for each category
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
            "hr": float(row["hr"]),
            "avg": round(float(row["avg"]), 3),
            "ops": round(float(row["ops"]), 3),
        },
        "featured_stat": featured_stat,
    }