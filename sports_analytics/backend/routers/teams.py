from fastapi import APIRouter, HTTPException
from routers.scores import compute_full_scores
from datetime import datetime

router = APIRouter()


@router.get("/teams/rankings")
def team_rankings():
    """
    Rank today's teams by the average model score of their projected
    hitters — a quick signal for moneyline shopping. Uses the same fully-scored
    total (real H2H, splits and bonuses) as the Top 25 board so a player's
    score is identical across every tab.
    """
    try:
        full = compute_full_scores()
        games = full["games"]
        all_players = full["all_players"]

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
        team_players: dict = {}
        # Dedupe by player: on a double-header a hitter appears once per game,
        # which would otherwise double every count and the roster list.
        seen_players: set = set()
        for player in all_players:
            if player["player_id"] in seen_players:
                continue
            seen_players.add(player["player_id"])
            score = player.get("total_score", player["pre_h2h_score"])
            team_scores.setdefault(player["team"], []).append(score)
            team_players.setdefault(player["team"], []).append({
                "player_id": player["player_id"],
                "name": player["name"],
                "score": score,
            })

        rankings = []
        for team_name, scores in team_scores.items():
            info = team_info.get(team_name, {})
            players = sorted(
                team_players.get(team_name, []),
                key=lambda p: p["score"],
                reverse=True,
            )
            rankings.append({
                "team_id": info.get("team_id"),
                "team_name": team_name,
                "opponent": info.get("opponent"),
                "venue": info.get("venue"),
                "side": info.get("side"),
                "avg_score": round(sum(scores) / len(scores), 2),
                "player_count": len(scores),
                "players": players,
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
