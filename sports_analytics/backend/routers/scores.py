from fastapi import APIRouter, HTTPException
from services.scoring import (
    fetch_all_season_stats,
    fetch_all_10day_stats,
    fetch_bullpen_eras,
    fetch_todays_games,
    fetch_todays_lineups,
    fetch_recent_appearances_batch,
    fetch_h2h,
    fetch_splits,
    score_player,
    score_10day_stats,
    score_season_stats,
    score_season_hr_rate,
    score_h2h,
    score_lr_splits,
    score_park_factor,
    score_weather,
    score_bullpen,
)
from services.weather import get_weather_for_venue
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

router = APIRouter()


def build_shared_data(year: int) -> dict:
    all_season = fetch_all_season_stats(year)
    all_10day = fetch_all_10day_stats(year)
    all_bullpen_eras = fetch_bullpen_eras(year)
    all_split_ops = [
        {"avg": p["avg"], "ops": p["ops"]} for p in all_season
    ]

    return {
        "all_season": all_season,
        "all_10day": all_10day,
        "all_h2h_ops": [],        # kept for backwards compat but unused
        "all_split_ops": all_split_ops,
        "all_bullpen_eras": all_bullpen_eras,
    }


def collect_todays_matchups(
    games: list,
    shared: dict,
    lineups: dict,
    check_all_unposted_teams: bool,
) -> tuple:
    """
    Build the list of batter-vs-starter matchups for today's slate,
    applying the lineup filter:
      - Team lineup posted: batter must be in it.
      - Lineup not posted: batter must have appeared in the last 3 days.
        `check_all_unposted_teams=False` mirrors the classic endpoint,
        which only runs the appearance check when *no* lineup is posted
        anywhere; `True` checks each lineup-less team individually.

    Returns (matchups, lineup_posted). Matchup order matches the original
    per-game away-then-home iteration so downstream sorts stay stable.
    """
    lineup_posted = len(lineups) > 0

    season_by_team: dict = {}
    for p in shared["all_season"]:
        season_by_team.setdefault(p["team_id"], []).append(p)

    candidates = []
    for game in games:
        venue = game["venue"]
        home_pitcher = game.get("home_probable_pitcher")
        away_pitcher = game.get("away_probable_pitcher")

        for side, pitcher, opp_team_id in [
            ("away", home_pitcher, game["home_team_id"]),
            ("home", away_pitcher, game["away_team_id"]),
        ]:
            if not pitcher:
                continue

            pitcher_hand = pitcher.get("pitchHand", {}).get("code", "R")
            team_id = game["home_team_id"] if side == "home" \
                else game["away_team_id"]
            team_name = game["home_team_name"] if side == "home" \
                else game["away_team_name"]

            batters = season_by_team.get(team_id, [])[:9]

            for batter in batters:
                batter_hand = batter.get("bats", "R")
                if batter_hand == "S":
                    batter_hand = "L" if pitcher_hand == "R" else "R"

                candidates.append({
                    "game_id": game["game_id"],
                    "venue": venue,
                    "side": side,
                    "team_id": team_id,
                    "team_name": team_name,
                    "opp_team_id": opp_team_id,
                    "pitcher": pitcher,
                    "pitcher_id": pitcher["id"],
                    "pitcher_hand": pitcher_hand,
                    "batter": batter,
                    "player_id": batter["player_id"],
                    "batter_hand": batter_hand,
                })

    # Batch the recent-appearance check for players whose team hasn't
    # posted a lineup (much faster than one request per player).
    unposted_pids = [
        c["player_id"] for c in candidates
        if lineups.get(c["team_id"]) is None
    ]
    if check_all_unposted_teams:
        recent_appearances = fetch_recent_appearances_batch(
            unposted_pids, days=3
        ) if unposted_pids else {}
    else:
        recent_appearances = fetch_recent_appearances_batch(
            unposted_pids, days=3
        ) if not lineup_posted else {}

    matchups = []
    for c in candidates:
        team_lineup = lineups.get(c["team_id"])
        if team_lineup is not None:
            if c["player_id"] not in team_lineup:
                continue
        else:
            if recent_appearances.get(c["player_id"], 0) == 0:
                continue
        c["in_lineup"] = team_lineup is not None
        matchups.append(c)

    return matchups, lineup_posted


def prefetch_h2h_and_splits(
    matchups: list, year: int, max_workers: int = 20
) -> dict:
    """
    Fetch H2H and L/R splits for every matchup concurrently.
    Returns {(player_id, pitcher_id): {"h2h": ..., "splits": ...}}.
    """
    results = {}

    def fetch_one(m):
        key = (m["player_id"], m["pitcher_id"])
        h2h = fetch_h2h(m["player_id"], m["pitcher_id"])
        splits = fetch_splits(m["player_id"], year)
        return key, {"h2h": h2h, "splits": splits}

    unique = {
        (m["player_id"], m["pitcher_id"]): m for m in matchups
    }

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(fetch_one, m) for m in unique.values()
        ]
        for future in as_completed(futures):
            try:
                key, data = future.result()
                results[key] = data
            except Exception:
                continue

    return results


@router.get("/scores/today")
def todays_scores():
    try:
        year = datetime.now().year
        games = fetch_todays_games()
        shared = build_shared_data(year)

        # Fetch confirmed lineups
        lineups = fetch_todays_lineups()

        matchups, lineup_posted = collect_todays_matchups(
            games, shared, lineups, check_all_unposted_teams=False
        )

        # Fetch every matchup's H2H + splits concurrently up front —
        # this was previously done one player at a time.
        prefetched = prefetch_h2h_and_splits(matchups, year)

        matchups_by_game: dict = {}
        for m in matchups:
            matchups_by_game.setdefault(m["game_id"], []).append(m)

        results = []

        for game in games:
            venue = game["venue"]
            home_pitcher = game.get("home_probable_pitcher")
            away_pitcher = game.get("away_probable_pitcher")
            weather = get_weather_for_venue(venue)

            game_scores = {
                "game_id": game["game_id"],
                "venue": venue,
                "home_team": game["home_team_name"],
                "away_team": game["away_team_name"],
                "home_probable_pitcher": {
                    "id": home_pitcher["id"] if home_pitcher else None,
                    "name": home_pitcher.get("fullName") if home_pitcher else None,
                },
                "away_probable_pitcher": {
                    "id": away_pitcher["id"] if away_pitcher else None,
                    "name": away_pitcher.get("fullName") if away_pitcher else None,
                },
                "weather": weather,
                "lineup_posted": lineup_posted,
                "players": [],
            }

            for m in matchups_by_game.get(game["game_id"], []):
                try:
                    pdata = prefetched.get(
                        (m["player_id"], m["pitcher_id"]), {}
                    )
                    result = score_player(
                        player_id=m["player_id"],
                        venue=venue,
                        batter_hand=m["batter_hand"],
                        pitcher_id=m["pitcher_id"],
                        pitcher_hand=m["pitcher_hand"],
                        opp_team_id=m["opp_team_id"],
                        weather=weather,
                        splits=pdata.get("splits"),
                        h2h=pdata.get("h2h"),
                        **shared,
                    )
                    result["name"] = m["batter"]["name"]
                    result["team"] = m["team_name"]
                    result["side"] = m["side"]
                    result["bats"] = m["batter_hand"]
                    result["in_lineup"] = m["in_lineup"]
                    game_scores["players"].append(result)
                except Exception:
                    continue

            game_scores["players"].sort(
                key=lambda x: x["total_score"], reverse=True
            )
            results.append(game_scores)

        all_players = []
        for game in results:
            all_players.extend(game["players"])
        all_players.sort(key=lambda x: x["total_score"], reverse=True)

        return {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "lineup_posted": lineup_posted,
            "games": results,
            "top_25": all_players[:25],
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scores/player/{player_id}")
def score_single_player(player_id: int, pitcher_id: int, venue: str):
    """
    Score a single player given a pitcher and venue.
    Useful for testing individual scores.
    Example: /api/scores/player/592450?pitcher_id=543037&venue=Yankee+Stadium
    """
    try:
        year = datetime.now().year
        shared = build_shared_data(year)
        weather = get_weather_for_venue(venue)

        result = score_player(
            player_id=player_id,
            venue=venue,
            batter_hand="R",
            pitcher_id=pitcher_id,
            pitcher_hand="R",
            opp_team_id=0,
            weather=weather,
            **shared,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def compute_fast_scores() -> dict:
    """
    Score every projected starter for today without H2H (fast pass).
    Shared by /scores/today/fast and the team rankings endpoint.
    Returns {"games", "shared", "all_players"} where all_players is
    sorted by pre-H2H score, descending.
    """
    year = datetime.now().year
    games = fetch_todays_games()
    shared = build_shared_data(year)
    lineups = fetch_todays_lineups()

    matchups, _ = collect_todays_matchups(
        games, shared, lineups, check_all_unposted_teams=True
    )

    ten_day_by_id = {p["player_id"]: p for p in shared["all_10day"]}
    season_by_id = {p["player_id"]: p for p in shared["all_season"]}

    all_players = []

    for m in matchups:
        pid = m["player_id"]
        venue = m["venue"]
        weather = get_weather_for_venue(venue)

        try:
            ten_day = ten_day_by_id.get(pid, {"avg": 0.0, "ops": 0.0})
            season_stats = season_by_id.get(pid)

            if not season_stats:
                continue

            # Score WITHOUT H2H — use 50th percentile default
            core = {
                "ten_day": score_10day_stats(
                    ten_day, shared["all_10day"]
                ),
                "season": score_season_stats(
                    season_stats, shared["all_season"]
                ),
                "season_hr": score_season_hr_rate(
                    season_stats, shared["all_season"]
                ),
                "h2h": 20.0,  # placeholder
                "lr_splits": 14.0,  # placeholder
                "park_factor": score_park_factor(
                    venue, m["batter_hand"]
                ),
                "weather": score_weather(
                    weather.get("temp_f", 72),
                    weather.get("wind_speed", 0),
                    weather.get("wind_direction", "calm")
                ),
                "bullpen": score_bullpen(
                    m["opp_team_id"],
                    shared["all_bullpen_eras"]
                ),
            }

            all_players.append({
                "player_id": pid,
                "name": m["batter"]["name"],
                "team": m["team_name"],
                "pitcher_id": m["pitcher_id"],
                "pitcher_hand": m["pitcher_hand"],
                "venue": venue,
                "batter_hand": m["batter_hand"],
                "weather": weather,
                "opp_team_id": m["opp_team_id"],
                "core": core,
                "pre_h2h_score": round(
                    sum(core.values()), 2
                ),
            })
        except Exception:
            continue

    all_players.sort(
        key=lambda x: x["pre_h2h_score"], reverse=True
    )

    return {
        "games": games,
        "shared": shared,
        "all_players": all_players,
    }


@router.get("/scores/today/fast")
def todays_scores_fast():
    """
    Fast version of today's scores.
    Scores all players without H2H first, then enriches
    the top 50 with real H2H data.
    """
    try:
        fast = compute_fast_scores()
        shared = fast["shared"]
        all_players = fast["all_players"]

        # Enrich the top players with real H2H + splits data
        top_players = all_players[:50]

        all_h2h_ops = [
            p["ops"] for p in shared["all_season"]
        ]
        all_split_ops = [
            {"avg": p["avg"], "ops": p["ops"]}
            for p in shared["all_season"]
        ]

        def enrich_player(player):
            try:
                pid = player["player_id"]
                pitcher_id = player["pitcher_id"]
                pitcher_hand = player["pitcher_hand"]

                h2h = fetch_h2h(pid, pitcher_id)
                splits = fetch_splits(
                    pid, datetime.now().year
                )

                player["core"]["h2h"] = score_h2h(
                    h2h, all_h2h_ops
                )
                player["core"]["lr_splits"] = score_lr_splits(
                    splits, pitcher_hand, all_split_ops
                )
                player["h2h_detail"] = h2h
                player["h2h_note"] = \
                    "Defaulted to 50th percentile (< 6 PA)" \
                    if h2h["pa"] < 6 else None
                player["total_score"] = round(
                    sum(player["core"].values()), 2
                )
            except Exception:
                player["total_score"] = player["pre_h2h_score"]
            return player

        # Enrich concurrently
        with ThreadPoolExecutor(max_workers=5) as executor:
            enriched = list(executor.map(enrich_player, top_players))

        enriched.sort(
            key=lambda x: x.get("total_score", 0), reverse=True
        )

        return {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "total_players_scored": len(all_players),
            "top_25": enriched[:25],
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
