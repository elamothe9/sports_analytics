from fastapi import APIRouter, HTTPException
from routers.scores import compute_full_scores
from datetime import datetime

router = APIRouter()


@router.get("/matchups/rankings")
def matchup_rankings():
    """
    Rank today's games by the average model score of *every* projected hitter
    in the matchup — both lineups pooled together. A high combined average
    means both offenses project well, which is a quick signal for game-total
    (over/under) and game-line prediction, whereas team rankings only speak to
    one side.

    Uses the same fully-scored total (real H2H, splits and bonuses) as the Top
    25 board, so a player's score is identical across every tab.
    """
    try:
        full = compute_full_scores()
        games = full["games"]
        all_players = full["all_players"]

        # Canonical identity for each game so we can attach home/away labels,
        # venue and pitchers. Keyed by the unordered pair of team names plus the
        # game number (double-headers share a pair but differ by game number).
        game_map = {}
        for game in games:
            key = (
                frozenset({game["home_team_name"], game["away_team_name"]}),
                game.get("game_number", 1),
            )
            game_map[key] = game

        # Group hitters into their game, split by team. Dedupe by player within
        # a team+game so a hitter listed twice never inflates the average.
        groups: dict = {}
        for p in all_players:
            team = p.get("team")
            opp = p.get("opp_team")
            if not team or not opp:
                continue
            gnum = p.get("game_number", 1)
            key = (frozenset({team, opp}), gnum)

            group = groups.setdefault(key, {
                "game_number": gnum,
                "doubleheader": p.get("doubleheader", False),
                "venue": p.get("venue"),
                "teams": {},
            })
            tinfo = group["teams"].setdefault(team, {
                "scores": [],
                "players": [],
                "seen": set(),
            })
            if p["player_id"] in tinfo["seen"]:
                continue
            tinfo["seen"].add(p["player_id"])
            score = p.get("total_score", p["pre_h2h_score"])
            tinfo["scores"].append(score)
            tinfo["players"].append({
                "player_id": p["player_id"],
                "name": p["name"],
                "team": team,
                "score": score,
            })

        rankings = []
        for key, group in groups.items():
            game = game_map.get(key)
            teams_data = group["teams"]

            # Every hitter in the game, pooled — this is the ranking metric.
            all_scores = [
                s for t in teams_data.values() for s in t["scores"]
            ]
            if not all_scores:
                continue

            home_name = game["home_team_name"] if game else None
            away_name = game["away_team_name"] if game else None
            venue = game["venue"] if game else group.get("venue")

            team_summaries = []
            home_avg = away_avg = None
            for tname, t in teams_data.items():
                avg = round(sum(t["scores"]) / len(t["scores"]), 2)
                if tname == home_name:
                    side = "home"
                    home_avg = avg
                elif tname == away_name:
                    side = "away"
                    away_avg = avg
                else:
                    side = None
                team_summaries.append({
                    "team_name": tname,
                    "side": side,
                    "avg_score": avg,
                    "player_count": len(t["scores"]),
                    "players": sorted(
                        t["players"], key=lambda x: x["score"], reverse=True
                    ),
                })

            # Display away first, then home ("Away @ Home"); unknown sides last.
            side_order = {"away": 0, "home": 1}
            team_summaries.sort(
                key=lambda s: side_order.get(s["side"], 2)
            )

            if home_name and away_name:
                label = f"{away_name} @ {home_name}"
            else:
                label = " vs ".join(s["team_name"] for s in team_summaries)

            rankings.append({
                "matchup": label,
                "home_team": home_name,
                "away_team": away_name,
                "venue": venue,
                "game_number": group["game_number"],
                "doubleheader": group.get("doubleheader", False),
                "combined_avg": round(sum(all_scores) / len(all_scores), 2),
                "home_avg": home_avg,
                "away_avg": away_avg,
                "hitter_count": len(all_scores),
                "teams": team_summaries,
            })

        rankings.sort(key=lambda x: x["combined_avg"], reverse=True)
        for rank, m in enumerate(rankings, start=1):
            m["rank"] = rank

        return {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "matchup_count": len(rankings),
            "rankings": rankings,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
