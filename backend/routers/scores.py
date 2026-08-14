from fastapi import APIRouter, HTTPException
import requests
import os
from services.scoring import (
    fetch_all_season_stats,
    fetch_all_10day_stats,
    fetch_bullpen_eras,
    fetch_todays_games,
    fetch_todays_lineups,
    fetch_recent_appearances_batch,
    fetch_recent_game_appearances,
    fetch_h2h,
    fetch_splits,
    fetch_game_logs_for_date,
    fetch_scores_for_date,
    score_player,
    score_10day_stats,
    score_season_stats,
    score_season_hr_rate,
    score_h2h,
    score_lr_splits,
    score_park_factor,
    score_weather,
    score_bullpen,
    get_statcast_batter_cached,
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


@router.get("/scores/today")
def todays_scores():
    try:
        year = datetime.now().year
        games = fetch_todays_games()
        shared = build_shared_data(year)

        # Fetch confirmed lineups
        lineups = fetch_todays_lineups()
        lineup_posted = len(lineups) > 0

        # Get all unique player IDs we plan to score
        all_player_ids = [p["player_id"] for p in shared["all_season"]]

        # Batch fetch recent appearances only if lineups aren't all posted
        recent_appearances = fetch_recent_appearances_batch(
            all_player_ids, days=3
        ) if not lineup_posted else {}

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

            for side, pitcher, opp_team_id in [
                ("away", home_pitcher, game["home_team_id"]),
                ("home", away_pitcher, game["away_team_id"]),
            ]:
                if not pitcher:
                    continue

                pitcher_id = pitcher["id"]
                pitcher_hand = pitcher.get("pitchHand", {}).get("code", "R")
                team_id = game["home_team_id"] if side == "home" \
                    else game["away_team_id"]

                batters = [
                    p for p in shared["all_season"]
                    if p["team_id"] == team_id
                ][:9]

                for batter in batters:
                    pid = batter["player_id"]

                    # ── LINEUP FILTER ──────────────────────────────
                    team_lineup = lineups.get(team_id)

                    if team_lineup is not None:
                        # Lineup is posted — player must be in it
                        if pid not in team_lineup:
                            continue
                    else:
                        # Lineup not posted — player must have played
                        # in at least 1 of the last 3 days (covers 2 games)
                        games_played = recent_appearances.get(pid, 0)
                        if games_played == 0:
                            continue
                    # ───────────────────────────────────────────────

                    try:
                        batter_hand = batter.get("bats", "R")
                        if batter_hand == "S":
                            batter_hand = "L" if pitcher_hand == "R" else "R"

                        result = score_player(
                            player_id=pid,
                            venue=venue,
                            batter_hand=batter_hand,
                            pitcher_id=pitcher_id,
                            pitcher_hand=pitcher_hand,
                            opp_team_id=opp_team_id,
                            weather=weather,
                            **shared,
                        )
                        result["name"] = batter["name"]
                        result["team"] = game["home_team_name"] \
                            if side == "home" else game["away_team_name"]
                        result["side"] = side
                        result["bats"] = batter_hand
                        result["in_lineup"] = team_lineup is not None
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


@router.get("/scores/today/fast")
def todays_scores_fast():
    """
    Fast version of today's scores.
    Scores all players without H2H first, then enriches
    the top 50 with real H2H data.
    """
    try:
        year = datetime.now().year
        games = fetch_todays_games()
        shared = build_shared_data(year)
        lineups = fetch_todays_lineups()

        all_players = []

        for game in games:
            venue = game["venue"]
            home_pitcher = game.get("home_probable_pitcher")
            away_pitcher = game.get("away_probable_pitcher")
            weather = get_weather_for_venue(venue)

            for side, pitcher, opp_team_id in [
                ("away", home_pitcher, game["home_team_id"]),
                ("home", away_pitcher, game["away_team_id"]),
            ]:
                if not pitcher:
                    continue

                pitcher_id = pitcher["id"]
                pitcher_hand = pitcher.get(
                    "pitchHand", {}
                ).get("code", "R")
                team_id = game["home_team_id"] if side == "home" \
                    else game["away_team_id"]

                batters = [
                    p for p in shared["all_season"]
                    if p["team_id"] == team_id
                ][:9]

                for batter in batters:
                    pid = batter["player_id"]

                    # Lineup filter
                    team_lineup = lineups.get(int(team_id))
                    if team_lineup is not None:
                        if pid not in team_lineup:
                            continue
                    else:
                        games_played = fetch_recent_game_appearances(
                            pid, days=3
                        )
                        if games_played == 0:
                            continue

                    try:
                        batter_hand = batter.get("bats", "R")
                        if batter_hand == "S":
                            batter_hand = "L" \
                                if pitcher_hand == "R" else "R"

                        ten_day = next(
                            (p for p in shared["all_10day"]
                             if p["player_id"] == pid),
                            {"avg": 0.0, "ops": 0.0}
                        )
                        season_stats = next(
                            (p for p in shared["all_season"]
                             if p["player_id"] == pid),
                            None
                        )

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
                                venue, batter_hand
                            ),
                            "weather": score_weather(
                                weather.get("temp_f", 72),
                                weather.get("wind_speed", 0),
                                weather.get("wind_direction", "calm")
                            ),
                            "bullpen": score_bullpen(
                                opp_team_id,
                                shared["all_bullpen_eras"]
                            ),
                        }

                        all_players.append({
                            "player_id": pid,
                            "name": batter["name"],
                            "team": game["home_team_name"]
                                if side == "home"
                                else game["away_team_name"],
                            "pitcher_id": pitcher_id,
                            "pitcher_hand": pitcher_hand,
                            "venue": venue,
                            "batter_hand": batter_hand,
                            "weather": weather,
                            "opp_team_id": opp_team_id,
                            "core": core,
                            "pre_h2h_score": round(
                                sum(core.values()), 2
                            ),
                        })
                    except Exception:
                        continue

        # Sort by pre-H2H score and enrich top 50 with real data
        all_players.sort(
            key=lambda x: x["pre_h2h_score"], reverse=True
        )
        top_players = all_players[:50]

        print(f"Enriching top {len(top_players)} players with H2H...")

        def enrich_player(player):
            try:
                pid = player["player_id"]
                pitcher_id = player["pitcher_id"]
                pitcher_hand = player["pitcher_hand"]
                batter_hand = player["batter_hand"]
                venue = player["venue"]
                weather = player["weather"]
                opp_team_id = player["opp_team_id"]

                h2h = fetch_h2h(pid, pitcher_id)
                splits = fetch_splits(
                    pid, datetime.now().year
                )

                all_h2h_ops = [
                    p["ops"] for p in shared["all_season"]
                ]
                all_split_ops = [
                    {"avg": p["avg"], "ops": p["ops"]}
                    for p in shared["all_season"]
                ]

                player["core"]["h2h"] = score_h2h(
                    h2h
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


@router.get("/scores/today/fast")
def todays_scores_fast():
    """
    Fast version of today's scores.
    Scores all players without H2H first, then enriches
    the top 50 with real H2H data.
    """
    try:
        year = datetime.now().year
        games = fetch_todays_games()
        shared = build_shared_data(year)
        lineups = fetch_todays_lineups()

        all_players = []

        for game in games:
            venue = game["venue"]
            home_pitcher = game.get("home_probable_pitcher")
            away_pitcher = game.get("away_probable_pitcher")
            weather = get_weather_for_venue(venue)

            for side, pitcher, opp_team_id in [
                ("away", home_pitcher, game["home_team_id"]),
                ("home", away_pitcher, game["away_team_id"]),
            ]:
                if not pitcher:
                    continue

                pitcher_id = pitcher["id"]
                pitcher_hand = pitcher.get(
                    "pitchHand", {}
                ).get("code", "R")
                team_id = game["home_team_id"] if side == "home" \
                    else game["away_team_id"]

                batters = [
                    p for p in shared["all_season"]
                    if p["team_id"] == team_id
                ][:9]

                for batter in batters:
                    pid = batter["player_id"]

                    # Lineup filter
                    team_lineup = lineups.get(int(team_id))
                    if team_lineup is not None:
                        if pid not in team_lineup:
                            continue
                    else:
                        games_played = fetch_recent_game_appearances(
                            pid, days=3
                        )
                        if games_played == 0:
                            continue

                    try:
                        batter_hand = batter.get("bats", "R")
                        if batter_hand == "S":
                            batter_hand = "L" \
                                if pitcher_hand == "R" else "R"

                        ten_day = next(
                            (p for p in shared["all_10day"]
                             if p["player_id"] == pid),
                            {"avg": 0.0, "ops": 0.0}
                        )
                        season_stats = next(
                            (p for p in shared["all_season"]
                             if p["player_id"] == pid),
                            None
                        )

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
                                venue, batter_hand
                            ),
                            "weather": score_weather(
                                weather.get("temp_f", 72),
                                weather.get("wind_speed", 0),
                                weather.get("wind_direction", "calm")
                            ),
                            "bullpen": score_bullpen(
                                opp_team_id,
                                shared["all_bullpen_eras"]
                            ),
                        }

                        all_players.append({
                            "player_id": pid,
                            "name": batter["name"],
                            "team": game["home_team_name"]
                                if side == "home"
                                else game["away_team_name"],
                            "pitcher_id": pitcher_id,
                            "pitcher_hand": pitcher_hand,
                            "venue": venue,
                            "batter_hand": batter_hand,
                            "weather": weather,
                            "opp_team_id": opp_team_id,
                            "core": core,
                            "pre_h2h_score": round(
                                sum(core.values()), 2
                            ),
                        })
                    except Exception:
                        continue

        # Sort by pre-H2H score and enrich top 50 with real data
        all_players.sort(
            key=lambda x: x["pre_h2h_score"], reverse=True
        )
        top_players = all_players[:50]

        print(f"Enriching top {len(top_players)} players with H2H...")

        def enrich_player(player):
            try:
                pid = player["player_id"]
                pitcher_id = player["pitcher_id"]
                pitcher_hand = player["pitcher_hand"]
                batter_hand = player["batter_hand"]
                venue = player["venue"]
                weather = player["weather"]
                opp_team_id = player["opp_team_id"]

                h2h = fetch_h2h(pid, pitcher_id)
                splits = fetch_splits(
                    pid, datetime.now().year
                )

                all_h2h_ops = [
                    p["ops"] for p in shared["all_season"]
                ]
                all_split_ops = [
                    {"avg": p["avg"], "ops": p["ops"]}
                    for p in shared["all_season"]
                ]

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

@router.get("/debug/10day")
def debug_10day():
    from services.scoring import fetch_all_10day_stats
    data = fetch_all_10day_stats(datetime.now().year)
    return {"count": len(data), "sample": data[:3]}


@router.get("/debug/bullpen")
def debug_bullpen():
    from services.scoring import fetch_bullpen_eras
    from datetime import datetime
    eras = fetch_bullpen_eras(datetime.now().year)
    sorted_eras = sorted(eras.items(), key=lambda x: x[1])
    return {
        "total_teams": len(eras),
        "best_bullpens": sorted_eras[:5],   # lowest ERA = toughest for batters
        "worst_bullpens": sorted_eras[-5:],  # highest ERA = easiest for batters
        "all": eras,
    }


@router.get("/debug/gamelog")
def debug_gamelog(date: str = "2026-08-09"):
    from services.scoring import fetch_game_logs_for_date
    results = fetch_game_logs_for_date(date)
    return {
        "date": date,
        "players_found": len(results),
        "sample": dict(list(results.items())[:3])
    }


@router.get("/debug/gamelog/raw")
def debug_gamelog_raw(date: str = "2026-08-09"):
    import requests
    url = "https://statsapi.mlb.com/api/v1/schedule"
    params = {
        "sportId": 1,
        "date": date,
        "hydrate": "boxscore",
    }
    res = requests.get(url, params=params, timeout=15)
    data = res.json()
    dates = data.get("dates", [])
    if not dates:
        return {"error": "no dates found"}
    games = dates[0].get("games", [])
    if not games:
        return {"error": "no games found"}
    # Return just the first game's top-level keys so we can see the structure
    first_game = games[0]
    return {
        "top_level_keys": list(first_game.keys()),
        "teams_keys": list(first_game.get("teams", {}).keys()),
        "has_liveData": "liveData" in first_game,
        "has_boxscore": "boxscore" in first_game,
    }


@router.get("/debug/gamelog/v2")
def debug_gamelog_v2(date: str = "2026-08-09"):
    from services.scoring import fetch_game_logs_for_date
    results = fetch_game_logs_for_date(date)
    sample = dict(list(results.items())[:5])
    return {
        "date": date,
        "players_found": len(results),
        "sample": sample
    }


@router.get("/debug/lineups")
def debug_lineups():
    from services.scoring import fetch_todays_lineups
    lineups = fetch_todays_lineups()
    return {
        "teams_with_lineups": len(lineups),
        "team_ids": list(lineups.keys()),
        "sample": {
            str(k): v[:5] for k, v in list(lineups.items())[:3]
        }
    }


@router.get("/debug/lineups/raw")
def debug_lineups_raw():
    import requests
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    url = "https://statsapi.mlb.com/api/v1/schedule"
    params = {
        "sportId": 1,
        "date": today,
        "hydrate": "lineups",
    }
    res = requests.get(url, params=params, timeout=15)
    data = res.json()
    dates = data.get("dates", [])
    if not dates:
        return {"error": "no dates"}
    games = dates[0].get("games", [])
    if not games:
        return {"error": "no games"}
    first_game = games[0]
    home = first_game["teams"]["home"]
    return {
        "home_team": home["team"]["name"],
        "home_keys": list(home.keys()),
        "has_lineup": "lineup" in home,
        "lineup_sample": home.get("lineup", [])[:3],
    }


@router.get("/debug/h2h")
def debug_h2h(batter_id: int, pitcher_id: int):
    from services.scoring import fetch_h2h
    result = fetch_h2h(batter_id, pitcher_id)
    return result


@router.get("/debug/h2h/raw")
def debug_h2h_raw(batter_id: int, pitcher_id: int):
    import requests
    url = "https://statsapi.mlb.com/api/v1/stats"
    params = {
        "stats": "vsPlayer",
        "group": "hitting",
        "playerId": batter_id,
        "opposingPlayerId": pitcher_id,
        "sportId": 1,
    }
    res = requests.get(url, params=params, timeout=15)
    data = res.json()
    return {
        "status_code": res.status_code,
        "raw": data
    }


@router.get("/debug/h2h/pybaseball")
def debug_h2h_pybaseball(batter_id: int, pitcher_id: int):
    try:
        from pybaseball import statcast_batter_vs_pitcher
        df = statcast_batter_vs_pitcher(batter_id, pitcher_id)
        if df is None or df.empty:
            return {
                "status": "empty dataframe",
                "shape": None,
                "columns": None,
            }
        return {
            "status": "data returned",
            "shape": df.shape,
            "columns": list(df.columns),
            "sample_events": df["events"].dropna().unique().tolist()[:10],
            "row_count": len(df),
        }
    except Exception as e:
        return {"status": "exception", "error": str(e)}


@router.get("/debug/pybaseball/functions")
def debug_pybaseball_functions():
    import pybaseball
    functions = [f for f in dir(pybaseball) if not f.startswith("_")]
    return {"functions": functions}


@router.get("/debug/h2h/verbose")
def debug_h2h_verbose(batter_id: int, pitcher_id: int):
    try:
        from pybaseball import statcast_batter
        from datetime import datetime

        start = "2015-01-01"
        end = datetime.now().strftime("%Y-%m-%d")

        print(f"Fetching statcast data for batter {batter_id}...")
        df = statcast_batter(start, end, player_id=batter_id)

        if df is None or df.empty:
            return {"step": "fetch", "status": "empty", "rows": 0}

        print(f"Got {len(df)} rows. Filtering for pitcher {pitcher_id}...")

        # Check what the pitcher column looks like
        pitcher_col_sample = df["pitcher"].head(5).tolist() if "pitcher" in df.columns else "NO PITCHER COLUMN"

        filtered = df[df["pitcher"] == pitcher_id]

        return {
            "step": "complete",
            "total_rows": len(df),
            "pitcher_col_sample": pitcher_col_sample,
            "pitcher_id_type": str(type(pitcher_id)),
            "pitcher_col_type": str(df["pitcher"].dtype),
            "filtered_rows": len(filtered),
            "columns": list(df.columns[:10]),
        }

    except Exception as e:
        return {"step": "exception", "error": str(e), "type": str(type(e))}


@router.get("/debug/h2h/score")
def debug_h2h_score(batter_id: int, pitcher_id: int):
    from services.scoring import fetch_h2h, score_h2h, LEAGUE_AVG_OPS
    h2h = fetch_h2h(batter_id, pitcher_id)
    score = score_h2h(h2h)
    return {
        "h2h": h2h,
        "league_avg_ops": LEAGUE_AVG_OPS,
        "score": score,
        "expected": round(
            max(0.0, min(40.0, 20.0 + ((h2h["ops"] or 0) - LEAGUE_AVG_OPS) / 0.100 * 8.0)), 2
        ) if h2h["pa"] >= 6 else 20.0
    }


@router.get("/debug/pitcher/verify")
def debug_pitcher_verify(pitcher_id: int):
    import requests
    url = f"https://statsapi.mlb.com/api/v1/people/{pitcher_id}"
    res = requests.get(url, timeout=10)
    data = res.json()
    people = data.get("people", [])
    if not people:
        return {"error": "pitcher not found"}
    person = people[0]
    return {
        "id": person.get("id"),
        "fullName": person.get("fullName"),
        "pitchHand": person.get("pitchHand", {}).get("code"),
        "birthDate": person.get("birthDate"),
        "currentTeam": person.get("currentTeam", {}).get("name"),
    }


@router.get("/debug/h2h/events")
def debug_h2h_events(batter_id: int, pitcher_id: int):
    from services.scoring import get_statcast_batter_cached
    import pandas as pd

    df = get_statcast_batter_cached(batter_id)

    if df.empty:
        return {"error": "no data"}

    df = df.copy()
    df["pitcher"] = pd.to_numeric(
        df["pitcher"], errors="coerce"
    ).astype("Int64")
    filtered = df[df["pitcher"] == int(pitcher_id)]

    if filtered.empty:
        return {"error": "no matchup data"}

    pa_events = filtered[filtered["events"].notna()]

    return {
        "total_pitches": len(filtered),
        "plate_appearances": len(pa_events),
        "events": pa_events[[
            "game_date", "events", "description"
        ]].to_dict(orient="records"),
        "game_dates": filtered["game_date"].unique().tolist(),
    }


@router.get("/debug/odds/sports")
def debug_odds_sports():
    """Check what sports and markets are available on your plan."""
    import os
    api_key = os.getenv("ODDS_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="ODDS_API_KEY not set in .env")

    res = requests.get(
        "https://api.the-odds-api.com/v4/sports",
        params={"apiKey": api_key},
        timeout=10
    )
    data = res.json()

    # Show remaining quota
    quota_remaining = res.headers.get("x-requests-remaining", "unknown")
    quota_used = res.headers.get("x-requests-used", "unknown")

    return {
        "quota_used": quota_used,
        "quota_remaining": quota_remaining,
        "mlb_available": any(
            s.get("key") == "baseball_mlb" for s in data
        ),
        "sports": [
            s for s in data if "baseball" in s.get("key", "")
        ],
    }


@router.get("/debug/odds/markets")
def debug_odds_markets():
    """Fetch today's MLB odds and see what markets are available."""
    api_key = os.getenv("ODDS_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500, detail="ODDS_API_KEY not set"
        )

    # Fetch today's MLB games with available markets
    res = requests.get(
        "https://api.the-odds-api.com/v4/sports/baseball_mlb/odds",
        params={
            "apiKey": api_key,
            "regions": "us",
            "markets": "h2h,totals",
            "oddsFormat": "american",
        },
        timeout=15
    )

    quota_remaining = res.headers.get("x-requests-remaining", "?")
    data = res.json()

    if not data:
        return {"error": "no games found", "quota_remaining": quota_remaining}

    # Show first game's structure so we know what we're working with
    first_game = data[0]
    return {
        "quota_remaining": quota_remaining,
        "quota_used": res.headers.get("x-requests-used", "?"),
        "games_today": len(data),
        "sample_game": {
            "id": first_game.get("id"),
            "home": first_game.get("home_team"),
            "away": first_game.get("away_team"),
            "commence": first_game.get("commence_time"),
            "bookmakers": [
                b.get("key") for b in first_game.get("bookmakers", [])
            ],
            "markets_available": [
                m.get("key")
                for b in first_game.get("bookmakers", [])[:1]
                for m in b.get("markets", [])
            ],
        },
    }