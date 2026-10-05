from fastapi import APIRouter, HTTPException
from services.stats import get_leaders
from services.scoring import (
    fetch_all_10day_stats,
    fetch_all_season_stats,
    fetch_team_map,
    fetch_batter_recent_games,
)
from datetime import datetime

router = APIRouter()


@router.get("/leaders")
def leaders():
    try:
        data = get_leaders()
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _running_series(games: list, stat: str) -> list:
    """
    Build the running trend of `stat` across the games (oldest -> newest):
      hr  -> cumulative home-run count
      avg -> cumulative batting average through each game
      ops -> cumulative OBP + SLG through each game
    """
    cum_h = cum_ab = cum_hr = cum_bb = cum_hbp = cum_sf = cum_tb = 0
    out = []
    for g in games:
        cum_h += g["hits"]; cum_ab += g["ab"]; cum_hr += g["hr"]
        cum_bb += g["bb"]; cum_hbp += g["hbp"]; cum_sf += g["sf"]; cum_tb += g["tb"]
        if stat == "hr":
            out.append(cum_hr)
        elif stat == "avg":
            out.append(round(cum_h / cum_ab, 3) if cum_ab else 0.0)
        else:  # ops
            obp_den = cum_ab + cum_bb + cum_hbp + cum_sf
            obp = (cum_h + cum_bb + cum_hbp) / obp_den if obp_den else 0.0
            slg = cum_tb / cum_ab if cum_ab else 0.0
            out.append(round(obp + slg, 3))
    return out


@router.get("/leaders/hot")
def hot_leaders():
    """
    Top AVG, HR and OPS hitters over the last 10 days, each with a running
    trend of that stat across their recent games (for the dashboard sparklines).
    """
    try:
        year = datetime.now().year
        ten = fetch_all_10day_stats(year)
        if not ten:
            return {"days": 10, "avg_leader": None,
                    "hr_leader": None, "ops_leader": None}

        season = {p["player_id"]: p for p in fetch_all_season_stats(year)}
        team_names = fetch_team_map()

        def leader(stat: str) -> dict:
            best = max(ten, key=lambda p: p.get(stat, 0) or 0)
            pid = best["player_id"]
            sinfo = season.get(pid, {})
            team_id = best.get("team_id") or sinfo.get("team_id")
            games = fetch_batter_recent_games(pid, year)
            return {
                "player_id": pid,
                "name": best.get("name") or sinfo.get("name") or "Unknown",
                "team": team_names.get(team_id, ""),
                "stat": stat,
                "value": best.get(stat),
                "pa": best.get("pa"),
                "series": _running_series(games, stat),
            }

        return {
            "days": 10,
            "avg_leader": leader("avg"),
            "hr_leader": leader("hr"),
            "ops_leader": leader("ops"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
