from fastapi import APIRouter, HTTPException
from routers.scores import compute_fast_scores
from datetime import datetime

router = APIRouter()


@router.get("/teams/rankings")
def team_rankings():
    """
    Rank today's teams by the average model score of their projected
    hitters — a quick signal for moneyline shopping.
    """
    try:
        fast = compute_fast_scores()
        games = fast["games"]
        all_players = fast["all_players"]

        team_info = {}
        for game in games:
            team_info[game["home_team_name"]] = {
                "team_id": game["home_team_id"],
                "opponent": game["away_team_name"],
                "venue": game["venue"],
                "side": "home",
            }
            team_info[game["away_team_name"]] = {
                "team_id": game["away_team_id"],
                "opponent": game["home_team_name"],
                "venue": game["venue"],
                "side": "away",
            }

        team_scores: dict = {}
        for player in all_players:
            team_scores.setdefault(player["team"], []).append(
                player["pre_h2h_score"]
            )

        rankings = []
        for team_name, scores in team_scores.items():
            info = team_info.get(team_name, {})
            rankings.append({
                "team_id": info.get("team_id"),
                "team_name": team_name,
                "opponent": info.get("opponent"),
                "venue": info.get("venue"),
                "side": info.get("side"),
                "avg_score": round(sum(scores) / len(scores), 2),
                "player_count": len(scores),
            })

        rankings.sort(key=lambda x: x["avg_score"], reverse=True)
        for rank, team in enumerate(rankings, start=1):
            team["rank"] = rank

        return {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "team_count": len(rankings),
            "rankings": rankings,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
