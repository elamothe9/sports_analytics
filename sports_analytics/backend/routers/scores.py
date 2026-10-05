from fastapi import APIRouter, HTTPException
from services.scoring import (
    fetch_all_season_stats,
    fetch_all_10day_stats,
    fetch_bullpen_eras,
    fetch_todays_games,
    fetch_todays_lineups,
    fetch_live_scoreboard,
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
    score_bonuses,
    active_bonus_list,
    gather_bonus_inputs,
)
from services.weather import get_weather_for_venue
from services.cache import ttl_cache
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


PROJECTED_LINEUP_SIZE = 11


def collect_todays_matchups(
    games: list,
    shared: dict,
    lineups: dict,
    check_all_unposted_teams: bool = True,
) -> tuple:
    """
    Build the list of batter-vs-starter matchups for today's slate.

      - Team lineup posted: use the posted batting order as-is.
      - Lineup not posted: PROJECT the lineup from recent (last-10-day) playing
        time — the top 11 hitters with the most plate appearances over the last 10
        days — rather than season-long plate appearances. Season totals miss
        hot call-ups and part-timers who have become everyday players recently
        (e.g. a rookie with 100 season PA but starting every day this week), so
        ranking by season PA and capping at 9 silently dropped them from the
        board. Recent PA is the right signal for "who is actually playing now".

    `check_all_unposted_teams` is retained for backward compatibility but no
    longer changes behavior: every un-posted team is projected individually
    from recent activity, and no per-player appearance request is needed.

    Returns (matchups, lineup_posted). Matchup order matches the original
    per-game away-then-home iteration so downstream sorts stay stable.
    """
    lineup_posted = len(lineups) > 0

    # Full per-team season lists (already sorted by season PA, descending) plus
    # a by-id lookup for handedness / identity. No longer capped at 9.
    season_by_team: dict = {}
    hitters_by_id: dict = {}
    for p in shared["all_season"]:
        season_by_team.setdefault(p["team_id"], []).append(p)
        hitters_by_id[p["player_id"]] = p

    # Recent activity: last-10-day hitters grouped by team, sorted by recent PA.
    # This is the basis for projecting a lineup that hasn't been posted yet.
    tenday_by_team: dict = {}
    tenday_by_id: dict = {}
    for p in shared.get("all_10day", []):
        tenday_by_id[p["player_id"]] = p
        if p.get("team_id") is not None:
            tenday_by_team.setdefault(p["team_id"], []).append(p)
    for tid in tenday_by_team:
        tenday_by_team[tid].sort(key=lambda x: x.get("pa", 0), reverse=True)

    def project_pool(team_id: int) -> list:
        """Projected batter ids for an un-posted team: the most recently-active
        hitters (top by last-10-day PA), topped up with season regulars if
        fewer than a full lineup have been active recently."""
        ids = [
            e["player_id"] for e in tenday_by_team.get(team_id, [])
        ][:PROJECTED_LINEUP_SIZE]
        if len(ids) < PROJECTED_LINEUP_SIZE:
            seen = set(ids)
            for p in season_by_team.get(team_id, []):
                if p["player_id"] not in seen:
                    ids.append(p["player_id"])
                    seen.add(p["player_id"])
                    if len(ids) >= PROJECTED_LINEUP_SIZE:
                        break
        return ids

    def batter_for(pid: int):
        """Resolve a player id to a batter record, preferring season stats and
        falling back to the last-10-day record for a very recent call-up that
        is under the season PA cutoff."""
        b = hitters_by_id.get(pid)
        if b is not None:
            return b
        t = tenday_by_id.get(pid)
        if t is not None:
            return {
                "player_id": pid,
                "name": t.get("name"),
                "team_id": t.get("team_id"),
                "avg": t.get("avg", 0.0),
                "ops": t.get("ops", 0.0),
                "hr": t.get("hr", 0),
                "pa": t.get("pa", 0),
                "bats": "R",
            }
        return None

    matchups = []
    for game in games:
        venue = game["venue"]
        home_pitcher = game.get("home_probable_pitcher")
        away_pitcher = game.get("away_probable_pitcher")

        for side, pitcher, opp_team_id, opp_team_name in [
            ("away", home_pitcher, game["home_team_id"], game["home_team_name"]),
            ("home", away_pitcher, game["away_team_id"], game["away_team_name"]),
        ]:
            if not pitcher:
                continue

            pitcher_hand = pitcher.get("pitchHand", {}).get("code", "R")
            team_id = game["home_team_id"] if side == "home" \
                else game["away_team_id"]
            team_name = game["home_team_name"] if side == "home" \
                else game["away_team_name"]

            team_lineup = lineups.get(team_id)
            if team_lineup:
                pool_ids = list(team_lineup)  # posted batting order, as-is
                in_lineup = True
            else:
                pool_ids = project_pool(team_id)  # projected from recent play
                in_lineup = False

            for pid in pool_ids:
                batter = batter_for(pid)
                if batter is None:
                    continue

                batter_hand = batter.get("bats", "R")
                if batter_hand == "S":
                    batter_hand = "L" if pitcher_hand == "R" else "R"

                matchups.append({
                    "game_id": game["game_id"],
                    "game_number": game.get("game_number", 1),
                    "doubleheader": game.get("doubleheader", False),
                    "game_date": game.get("game_date"),
                    "game_status": game.get("status"),
                    "abstract_state": game.get("abstract_state"),
                    "venue": venue,
                    "side": side,
                    "team_id": team_id,
                    "team_name": team_name,
                    "opp_team_id": opp_team_id,
                    "opp_team_name": opp_team_name,
                    "pitcher": pitcher,
                    "pitcher_id": pitcher["id"],
                    "pitcher_name": pitcher.get("fullName"),
                    "pitcher_hand": pitcher_hand,
                    "batter": batter,
                    "player_id": pid,
                    "batter_hand": batter_hand,
                    "in_lineup": in_lineup,
                })

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
        bonus_inputs = gather_bonus_inputs(
            m["player_id"], m["pitcher_id"],
            m["venue"], m["batter_hand"], year,
        )
        return key, {"h2h": h2h, "splits": splits, "bonus_inputs": bonus_inputs}

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
            weather = get_weather_for_venue(venue, game.get("game_date"))

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
                        **pdata.get("bonus_inputs", {}),
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
        weather = get_weather_for_venue(venue, m.get("game_date"))

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
                "pitcher_name": m.get("pitcher_name"),
                "pitcher_hand": m["pitcher_hand"],
                "venue": venue,
                "batter_hand": m["batter_hand"],
                "weather": weather,
                "opp_team_id": m["opp_team_id"],
                "opp_team": m.get("opp_team_name"),
                "game_number": m.get("game_number", 1),
                "doubleheader": m.get("doubleheader", False),
                "game_date": m.get("game_date"),
                "game_status": m.get("game_status"),
                "abstract_state": m.get("abstract_state"),
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


def _enrich_player(player: dict, all_h2h_ops: list, all_split_ops: list) -> dict:
    """
    Upgrade a fast (pre-H2H) player to a full score: replace the H2H and L/R
    split placeholders with real values and add situational bonuses, so
    ``total_score`` matches what the Top 25 board shows. On any failure the
    player keeps its pre-H2H score so it still ranks.
    """
    try:
        pid = player["player_id"]
        pitcher_id = player["pitcher_id"]
        pitcher_hand = player["pitcher_hand"]
        year = datetime.now().year

        h2h = fetch_h2h(pid, pitcher_id)
        splits = fetch_splits(pid, year)

        player["core"]["h2h"] = score_h2h(h2h, all_h2h_ops)
        player["core"]["lr_splits"] = score_lr_splits(
            splits, pitcher_hand, all_split_ops
        )
        player["h2h_detail"] = h2h
        player["h2h_note"] = (
            "Defaulted to 50th percentile (< 6 PA)"
            if h2h["pa"] < 6 else None
        )

        w = player.get("weather", {})
        bi = gather_bonus_inputs(
            pid, pitcher_id, player["venue"], player["batter_hand"], year
        )
        bonuses = score_bonuses(
            hit_streak=bi["hit_streak"],
            multi_hit_last_10=bi["multi_hit_last_10"],
            hr_last_3=bi["hr_last_3"],
            temp_f=w.get("temp_f", 72),
            wind_speed=w.get("wind_speed", 0),
            wind_direction=w.get("wind_direction", "calm"),
            career_avg_at_park=bi["career_avg_at_park"],
            park_favors_hand=bi["park_favors_hand"],
            pitcher_era_last_3=bi["pitcher_era_last_3"],
            h2h_ab=h2h.get("pa", 0),
            h2h_avg=h2h.get("avg", 0.0) or 0.0,
        )
        player["bonus_score"] = bonuses["total"]
        player["active_bonuses"] = active_bonus_list(bonuses)
        player["total_score"] = round(
            sum(player["core"].values()) + bonuses["total"], 2
        )
    except Exception:
        player["total_score"] = player["pre_h2h_score"]
        player.setdefault("bonus_score", 0.0)
        player.setdefault("active_bonuses", [])
    return player


@ttl_cache(seconds=360)
def compute_full_scores() -> dict:
    """
    Full board: EVERY projected hitter scored with real H2H, L/R splits and
    situational bonuses — the same ``total_score`` shown on the Top 25 board.
    Shared by the board and the team / matchup rankings so all three tabs report
    an identical score for any given player, instead of the board showing the
    full score while the rankings showed the cheaper pre-H2H placeholder score.

    Scoring the whole slate is expensive, so the result is cached and a startup
    warm-up plus a background refresher keep it hot — the dashboard is served
    from the warm cache instead of paying the enrichment cost on the request.
    """
    fast = compute_fast_scores()
    shared = fast["shared"]
    all_players = fast["all_players"]

    all_h2h_ops = [p["ops"] for p in shared["all_season"]]
    all_split_ops = [
        {"avg": p["avg"], "ops": p["ops"]} for p in shared["all_season"]
    ]

    with ThreadPoolExecutor(max_workers=8) as executor:
        enriched = list(executor.map(
            lambda p: _enrich_player(p, all_h2h_ops, all_split_ops),
            all_players,
        ))

    enriched.sort(key=lambda x: x.get("total_score", 0), reverse=True)

    return {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "games": fast["games"],
        "shared": shared,
        "all_players": enriched,
    }


@router.get("/scores/today/fast")
def todays_scores_fast():
    """
    Today's board: every projected hitter fully scored (real H2H, L/R splits and
    situational bonuses), sorted, top 25 returned. Backed by the shared,
    cached compute_full_scores() so the board and the team / matchup rankings
    all report the same score for a given player.
    """
    try:
        full = compute_full_scores()
        return {
            "date": full["date"],
            "total_players_scored": len(full["all_players"]),
            "top_25": full["all_players"][:25],
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scoreboard")
def live_scoreboard():
    """
    Live view of today's games — score, inning and status — for the scoreboard
    strip. Cached 30s so in-progress scores stay current.
    """
    try:
        return {
            "as_of": datetime.now().isoformat(timespec="seconds"),
            "games": fetch_live_scoreboard(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
