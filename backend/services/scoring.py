from datetime import datetime, timedelta
from scipy import stats
from concurrent.futures import ThreadPoolExecutor, as_completed
import numpy as np
import requests
import pandas as pd
import pickle
import os

CACHE_FILE = "statcast_cache.pkl"

def save_cache_to_disk():
    """Persist Statcast cache to disk."""
    try:
        with open(CACHE_FILE, "wb") as f:
            pickle.dump(_statcast_batter_cache, f)
        print(f"Saved {len(_statcast_batter_cache)} players to disk cache")
    except Exception as e:
        print(f"Failed to save cache: {e}")


def load_cache_from_disk():
    """Load persisted Statcast cache on server startup."""
    global _statcast_batter_cache
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "rb") as f:
                _statcast_batter_cache = pickle.load(f)
            print(f"Loaded {len(_statcast_batter_cache)} players from disk cache")
        except Exception as e:
            print(f"Failed to load cache: {e}")
            _statcast_batter_cache = {}
# ─────────────────────────────────────────────
# 2026 Park HR Factors (LHB and RHB)
# Source: fantasyteamadvice.com/mlb/park-factors
# ─────────────────────────────────────────────
PARK_FACTORS = {
    "American Family Field":       {"lhb": 1.00, "rhb": 1.03},
    "Angel Stadium of Anaheim":    {"lhb": 0.99, "rhb": 0.99},
    "Busch Stadium":               {"lhb": 0.99, "rhb": 0.93},
    "Chase Field":                 {"lhb": 1.07, "rhb": 1.03},
    "Citi Field":                  {"lhb": 0.92, "rhb": 0.95},
    "Citizens Bank Park":          {"lhb": 1.03, "rhb": 1.03},
    "Comerica Park":               {"lhb": 0.97, "rhb": 1.04},
    "Coors Field":                 {"lhb": 1.13, "rhb": 1.15},
    "Daikin Park":                 {"lhb": 0.97, "rhb": 0.98},
    "Dodger Stadium":              {"lhb": 1.02, "rhb": 0.99},
    "Ewing M. Kauffman Stadium":   {"lhb": 1.01, "rhb": 1.01},
    "Fenway Park":                 {"lhb": 1.12, "rhb": 1.03},
    "Globe Life Field":            {"lhb": 0.99, "rhb": 0.99},
    "Great American Ball Park":    {"lhb": 1.01, "rhb": 1.07},
    "Nationals Park":              {"lhb": 1.08, "rhb": 1.05},
    "Oracle Park":                 {"lhb": 1.00, "rhb": 1.00},
    "Oriole Park at Camden Yards": {"lhb": 1.03, "rhb": 1.01},
    "PETCO Park":                  {"lhb": 0.97, "rhb": 0.96},
    "PNC Park":                    {"lhb": 1.02, "rhb": 0.99},
    "Progressive Field":           {"lhb": 1.04, "rhb": 0.98},
    "Rate Field":                  {"lhb": 0.96, "rhb": 0.98},
    "Rogers Centre":               {"lhb": 1.02, "rhb": 1.04},
    "Sutter Health Park":          {"lhb": 1.04, "rhb": 1.05},
    "T-Mobile Park":               {"lhb": 0.95, "rhb": 0.95},
    "Target Field":                {"lhb": 1.01, "rhb": 1.04},
    "Tropicana Field":             {"lhb": 0.99, "rhb": 0.98},
    "Truist Park":                 {"lhb": 1.01, "rhb": 0.99},
    "Wrigley Field":               {"lhb": 1.01, "rhb": 1.02},
    "Yankee Stadium":              {"lhb": 0.99, "rhb": 0.98},
    "loanDepot Park":              {"lhb": 0.92, "rhb": 0.93},
}

MLB_API_BASE = "https://statsapi.mlb.com/api/v1"


# ─────────────────────────────────────────────
# Helper: percentile score
# ─────────────────────────────────────────────
def percentile_score(value: float, all_values: list, max_points: float) -> float:
    """Convert a raw value into a percentile-based point score."""
    if not all_values or len(all_values) < 2:
        return max_points * 0.5
    pct = stats.percentileofscore(all_values, value, kind="rank") / 100.0
    return round(pct * max_points, 2)


# ─────────────────────────────────────────────
# Data fetchers
# ─────────────────────────────────────────────
def fetch_all_season_stats(year: int) -> list:
    """Fetch season batting stats for all qualified hitters."""
    url = f"{MLB_API_BASE}/stats"
    params = {
        "stats": "season",
        "group": "hitting",
        "season": year,
        "playerPool": "ALL",
        "limit": 500,
        "sportId": 1,
        "sortStat": "plateAppearances",
        "order": "desc",
        "hydrate": "person",
    }
    res = requests.get(url, params=params)
    res.raise_for_status()
    splits = res.json()["stats"][0]["splits"]
    players = []
    for entry in splits:
        stat = entry["stat"]
        pa = int(stat.get("plateAppearances", 0) or 0)
        if pa < 50:
            continue

        person = entry.get("player", {})
        bats = person.get("batSide", {}).get("code", "R")

        players.append({
            "player_id": entry["player"]["id"],
            "name": entry["player"]["fullName"],
            "team_id": entry.get("team", {}).get("id"),
            "avg": float(stat.get("avg", 0) or 0),
            "ops": float(stat.get("ops", 0) or 0),
            "hr": int(stat.get("homeRuns", 0) or 0),
            "pa": pa,
            "bats": bats,
        })
    return players


def fetch_last_n_days_stats(player_id: int, days: int = 10) -> dict:
    """Fetch a single player's stats over the last N days."""
    end = datetime.now()
    start = end - timedelta(days=days)
    url = f"{MLB_API_BASE}/stats"
    params = {
        "stats": "byDateRange",
        "group": "hitting",
        "season": end.year,
        "startDate": start.strftime("%Y-%m-%d"),
        "endDate": end.strftime("%Y-%m-%d"),
        "playerPool": "ALL",
        "playerId": player_id,
        "sportId": 1,
    }
    res = requests.get(url, params=params)
    res.raise_for_status()
    data = res.json()
    splits = data.get("stats", [{}])[0].get("splits", [])
    if not splits:
        return {"avg": 0.0, "ops": 0.0, "hr": 0, "hits": 0, "ab": 0}
    stat = splits[0]["stat"]
    return {
        "avg": float(stat.get("avg", 0) or 0),
        "ops": float(stat.get("ops", 0) or 0),
        "hr": int(stat.get("homeRuns", 0) or 0),
        "hits": int(stat.get("hits", 0) or 0),
        "ab": int(stat.get("atBats", 0) or 0),
        "multi_hit_games": int(stat.get("totalGames", 0) or 0),
    }


def fetch_all_10day_stats(year: int) -> list:
    end = datetime.now()
    start = end - timedelta(days=10)
    url = f"{MLB_API_BASE}/stats"
    params = {
        "stats": "byDateRange",
        "group": "hitting",
        "season": year,
        "startDate": start.strftime("%Y-%m-%d"),
        "endDate": end.strftime("%Y-%m-%d"),
        "playerPool": "ALL",
        "limit": 500,
        "sportId": 1,
    }
    res = requests.get(url, params=params)
    res.raise_for_status()
    splits = res.json().get("stats", [{}])[0].get("splits", [])
    players = []
    for entry in splits:
        stat = entry["stat"]
        pa = int(stat.get("plateAppearances", 0) or 0)
        if pa < 30:                      # UPDATED threshold
            continue
        players.append({
            "player_id": entry["player"]["id"],
            "avg": float(stat.get("avg", 0) or 0),
            "ops": float(stat.get("ops", 0) or 0),
            "pa": pa,                    # ADDED for transparency
        })
    return players


def fetch_splits(player_id: int, year: int) -> dict:
    """Fetch L/R splits for a batter."""
    url = f"{MLB_API_BASE}/stats"
    params = {
        "stats": "statSplits",
        "group": "hitting",
        "season": year,
        "playerId": player_id,
        "sitCodes": "vl,vr",
        "sportId": 1,
    }
    res = requests.get(url, params=params)
    res.raise_for_status()
    splits = res.json().get("stats", [{}])[0].get("splits", [])
    result = {"vs_lhp": {"avg": 0.0, "ops": 0.0}, "vs_rhp": {"avg": 0.0, "ops": 0.0}}
    for s in splits:
        stat = s["stat"]
        code = s.get("split", {}).get("code", "")
        key = "vs_lhp" if code == "vl" else "vs_rhp"
        result[key] = {
            "avg": float(stat.get("avg", 0) or 0),
            "ops": float(stat.get("ops", 0) or 0),
        }
    return result


def fetch_h2h(batter_id: int, pitcher_id: int) -> dict:
    """
    Fetch career batter vs pitcher head-to-head stats.
    Uses cached Statcast data to avoid repeated slow fetches.
    """
    try:
        df = get_statcast_batter_cached(batter_id)

        if df.empty:
            return {"avg": None, "ops": None, "pa": 0}

        # Cast pitcher column to int regardless of source type
        # Statcast stores pitcher IDs as object/string in some versions
        df = df.copy()
        df["pitcher"] = pd.to_numeric(
            df["pitcher"], errors="coerce"
        ).astype("Int64")
        filtered = df[df["pitcher"] == int(pitcher_id)]

        if filtered.empty:
            return {"avg": None, "ops": None, "pa": 0}
        # Exclude spring training games
        if "game_type" in filtered.columns:
            filtered = filtered[filtered["game_type"] != "S"]

        if filtered.empty:
            return {"avg": None, "ops": None, "pa": 0}
        pa_events = filtered[filtered["events"].notna()]
        pa = len(pa_events)

        if pa == 0:
            return {"avg": None, "ops": None, "pa": 0}

        hit_events = ["single", "double", "triple", "home_run"]
        hits = pa_events[
            pa_events["events"].isin(hit_events)
        ].shape[0]

        non_ab_events = [
            "walk", "hit_by_pitch", "sac_fly",
            "sac_bunt", "intent_walk", "catcher_interf"
        ]
        ab = pa_events[
            ~pa_events["events"].isin(non_ab_events)
        ].shape[0]

        avg = round(hits / ab, 3) if ab > 0 else 0.0

        on_base_events = hit_events + [
            "walk", "hit_by_pitch", "intent_walk"
        ]
        on_base = pa_events[
            pa_events["events"].isin(on_base_events)
        ].shape[0]
        obp = round(on_base / pa, 3) if pa > 0 else 0.0

        singles = pa_events[
            pa_events["events"] == "single"
        ].shape[0]
        doubles = pa_events[
            pa_events["events"] == "double"
        ].shape[0]
        triples = pa_events[
            pa_events["events"] == "triple"
        ].shape[0]
        home_runs = pa_events[
            pa_events["events"] == "home_run"
        ].shape[0]
        total_bases = (
            singles + (2 * doubles) +
            (3 * triples) + (4 * home_runs)
        )
        slg = round(total_bases / ab, 3) if ab > 0 else 0.0
        ops = round(obp + slg, 3)

        return {
            "avg": avg,
            "ops": ops,
            "pa": pa,
            "ab": ab,
            "hits": hits,
        }

    except Exception as e:
        print(
            f"H2H fetch failed for {batter_id} vs {pitcher_id}: {e}"
        )
        return {"avg": None, "ops": None, "pa": 0}


def fetch_bullpen_eras(year: int) -> dict:
    """
    Fetch bullpen ERA for all 30 teams.
    Filters out starting pitchers by innings pitched threshold.
    Returns a dict of {team_id: bullpen_era}
    """
    url = f"{MLB_API_BASE}/stats"
    params = {
        "stats": "season",
        "group": "pitching",
        "season": year,
        "playerPool": "ALL",
        "limit": 1000,
        "sportId": 1,
        "sortStat": "inningsPitched",
        "order": "desc",
    }
    res = requests.get(url, params=params)
    res.raise_for_status()
    splits = res.json().get("stats", [{}])[0].get("splits", [])

    # Group relievers by team
    # A reliever is defined as a pitcher with fewer than 40 innings pitched
    # (starters typically exceed this over a full season)
    team_relievers = {}
    for entry in splits:
        stat = entry["stat"]
        team = entry.get("team", {})
        team_id = team.get("id")
        if not team_id:
            continue

        ip_str = stat.get("inningsPitched", "0.0") or "0.0"
        # IP is formatted as "45.2" meaning 45 and 2/3 innings
        try:
            ip_parts = str(ip_str).split(".")
            full_innings = int(ip_parts[0])
            partial = int(ip_parts[1]) if len(ip_parts) > 1 else 0
            ip = full_innings + partial / 3
        except (ValueError, IndexError):
            ip = 0.0

        # Skip starters (high IP) and pitchers with fewer than 5 IP (too small)
        if ip >= 40 or ip < 5:
            continue

        era = float(stat.get("era", 0) or 0)
        earned_runs = float(stat.get("earnedRuns", 0) or 0)

        if team_id not in team_relievers:
            team_relievers[team_id] = {"total_er": 0, "total_ip": 0}

        team_relievers[team_id]["total_er"] += earned_runs
        team_relievers[team_id]["total_ip"] += ip

    # Calculate weighted bullpen ERA per team
    # ERA = (earned runs / innings pitched) * 9
    bullpen_eras = {}
    for team_id, data in team_relievers.items():
        if data["total_ip"] > 0:
            era = (data["total_er"] / data["total_ip"]) * 9
            bullpen_eras[team_id] = round(era, 3)

    return bullpen_eras

def fetch_todays_games() -> list:
    """Fetch today's schedule with probable pitchers."""
    today = datetime.now().strftime("%Y-%m-%d")
    url = f"{MLB_API_BASE}/schedule"
    params = {
        "sportId": 1,
        "date": today,
        "hydrate": "probablePitcher,venue,team,lineups",
    }
    res = requests.get(url, params=params)
    res.raise_for_status()
    data = res.json()
    games = []
    for date in data.get("dates", []):
        for game in date.get("games", []):
            venue = game.get("venue", {}).get("name", "Unknown")
            home = game["teams"]["home"]
            away = game["teams"]["away"]
            games.append({
                "game_id": game["gamePk"],
                "venue": venue,
                "home_team_id": home["team"]["id"],
                "home_team_name": home["team"]["name"],
                "away_team_id": away["team"]["id"],
                "away_team_name": away["team"]["name"],
                "home_probable_pitcher": home.get("probablePitcher"),
                "away_probable_pitcher": away.get("probablePitcher"),
            })
    return games


# ─────────────────────────────────────────────
# Core scoring functions
# ─────────────────────────────────────────────

def score_10day_stats(player_10day: dict, all_10day: list) -> float:
    """Score based on last 10 days AVG and OPS — 50 points max."""
    if not player_10day or not all_10day:
        return 25.0  # 50th percentile default
    all_avgs = [p["avg"] for p in all_10day]
    all_ops = [p["ops"] for p in all_10day]
    avg_score = percentile_score(player_10day["avg"], all_avgs, 25)
    ops_score = percentile_score(player_10day["ops"], all_ops, 25)
    return avg_score + ops_score


def score_season_stats(player_season: dict, all_season: list) -> float:
    """Score based on full season AVG and OPS — 24 points max."""
    all_avgs = [p["avg"] for p in all_season]
    all_ops = [p["ops"] for p in all_season]
    avg_score = percentile_score(player_season["avg"], all_avgs, 12)
    ops_score = percentile_score(player_season["ops"], all_ops, 12)
    return avg_score + ops_score


# 2026 MLB league average OPS — update once per season
LEAGUE_AVG_OPS = 0.719

def score_h2h(h2h: dict, all_h2h_ops: list = None) -> float:
    """
    Score batter vs starting pitcher H2H — 40 points max.
    Compares H2H OPS against league average OPS rather than
    a percentile distribution, since H2H samples are too small
    and inconsistent for meaningful percentile ranking.

    Scoring:
    - Below 6 PA: defaults to 50th percentile (20 pts)
    - At league average OPS (.719): 20 pts (50th percentile)
    - Each .100 OPS above avg: +8 pts (capped at 40)
    - Each .100 OPS below avg: -4 pts (floored at 0)
    """
    if h2h["pa"] < 6 or h2h["ops"] is None:
        return 20.0  # neutral 50th percentile

    ops = h2h["ops"]
    diff = ops - LEAGUE_AVG_OPS

    # Scale: +/- .100 OPS = +8 / -4 points from baseline of 20
    points = 20.0 + (diff / 0.100) * 8.0

    # Cap between 0 and 40
    return round(max(0.0, min(40.0, points)), 2)


def score_lr_splits(splits: dict, pitcher_hand: str, all_split_ops: list) -> float:
    """Score L/R splits based on pitcher handedness — 28 points max."""
    key = "vs_lhp" if pitcher_hand == "L" else "vs_rhp"
    batter_ops = splits[key]["ops"]
    all_avgs = [p.get("avg", 0) for p in all_split_ops]
    all_ops_vals = [p.get("ops", 0) for p in all_split_ops]
    avg_score = percentile_score(splits[key]["avg"], all_avgs, 14)
    ops_score = percentile_score(batter_ops, all_ops_vals, 14)
    return avg_score + ops_score


def score_park_factor(venue: str, batter_hand: str) -> float:
    """Score park HR factor adjusted for batter handedness — 18 points max."""
    park = PARK_FACTORS.get(venue)
    if not park:
        return 9.0  # neutral if park not found
    hand_key = "lhb" if batter_hand == "L" else "rhb"
    factor = park[hand_key]
    # All factors range roughly 0.92–1.15
    # Map this range to 0–18 points
    min_factor = 0.92
    max_factor = 1.15
    normalized = (factor - min_factor) / (max_factor - min_factor)
    return round(normalized * 18, 2)


def score_weather(temp_f: float, wind_speed: float, wind_direction: str) -> float:
    """Score weather conditions — 14 points max (core), bonuses separate."""
    score = 0.0
    blowing_out = wind_direction.lower() in ["out", "out to cf", "out to lf", "out to rf"]

    # Temperature tiers
    if temp_f >= 85:
        score += 7
    elif temp_f >= 75:
        score += 5
    elif temp_f >= 65:
        score += 3
    elif temp_f >= 55:
        score += 1
    else:
        score += 0

    # Wind tiers (only if blowing out)
    if blowing_out:
        if wind_speed >= 15:
            score += 7
        elif wind_speed >= 10:
            score += 5
        elif wind_speed >= 5:
            score += 2
    return min(score, 14)


def score_bullpen(opp_team_id: int, all_bullpen_eras: dict) -> float:
    """Score opposing bullpen ERA — 14 points max. Higher ERA = more points for batter."""
    if not all_bullpen_eras:
        return 7.0  # neutral default
    era = all_bullpen_eras.get(opp_team_id, None)
    if era is None:
        return 7.0
    all_eras = list(all_bullpen_eras.values())
    # Invert — higher ERA is better for batter
    inverted = max(all_eras) - era
    all_inverted = [max(all_eras) - e for e in all_eras]
    return percentile_score(inverted, all_inverted, 14)


# ─────────────────────────────────────────────
# Bonus scoring
# ─────────────────────────────────────────────

def score_bonuses(
    hit_streak: int,
    multi_hit_last_10: int,
    hr_last_3: int,
    temp_f: float,
    wind_speed: float,
    wind_direction: str,
    career_avg_at_park: float | None,
    park_favors_hand: bool,
    pitcher_era_last_3: float | None,
    h2h_ab: int = 0,
    h2h_avg: float = 0.0,
) -> dict:
    """Calculate all bonus points. Returns a dict of each bonus and total."""
    bonuses = {}

    # Hit streak
    if hit_streak >= 9:
        bonuses["hit_streak"] = 7 + (hit_streak - 8)
    elif hit_streak == 8:
        bonuses["hit_streak"] = 7
    elif hit_streak >= 5:
        bonuses["hit_streak"] = 4
    else:
        bonuses["hit_streak"] = 0

    # Multi-hit games in last 10
    if multi_hit_last_10 >= 4:
        bonuses["multi_hit"] = 4 + (multi_hit_last_10 - 4) * 2
    else:
        bonuses["multi_hit"] = 0

    # HR in last 3 games (capped at +8)
    if hr_last_3 >= 1:
        bonuses["hr_last_3"] = min(2 + (hr_last_3 - 1) * 3, 8)
    else:
        bonuses["hr_last_3"] = 0

    # Weather bonuses
    blowing_out = wind_direction.lower() in ["out", "out to cf", "out to lf", "out to rf"]
    temp_bonus = 2 if temp_f >= 80 else 0
    wind_bonus = 3 if (blowing_out and wind_speed >= 10) else 0
    combo_bonus = 2 if (temp_bonus > 0 and wind_bonus > 0) else 0
    bonuses["weather"] = temp_bonus + wind_bonus + combo_bonus

    # Career AVG at park
    if career_avg_at_park is not None and career_avg_at_park >= 0.290:
        bonuses["career_at_park"] = 4
    else:
        bonuses["career_at_park"] = 0

    # Park favors handedness
    bonuses["park_hand_bonus"] = 4 if park_favors_hand else 0

    # Opposing starter recent ERA
    if pitcher_era_last_3 is not None:
        if pitcher_era_last_3 >= 7.0:
            bonuses["pitcher_era"] = 7
        elif pitcher_era_last_3 >= 5.5:
            bonuses["pitcher_era"] = 4
        else:
            bonuses["pitcher_era"] = 0
    else:
        bonuses["pitcher_era"] = 0

    bonuses["total"] = sum(bonuses.values())
    # Dominant H2H history — 10+ AB and .500+ BA against today's pitcher
    if h2h_ab >= 10 and h2h_avg >= 0.500:
        bonuses["dominant_h2h"] = 6
    else:
        bonuses["dominant_h2h"] = 0

    bonuses["total"] = sum(bonuses.values())
    return bonuses
    return bonuses


# ─────────────────────────────────────────────
# Main scoring entry point
# ─────────────────────────────────────────────

def score_player(
    player_id: int,
    venue: str,
    batter_hand: str,
    pitcher_id: int,
    pitcher_hand: str,
    opp_team_id: int,
    weather: dict,
    all_season: list,
    all_10day: list,
    all_h2h_ops: list,
    all_split_ops: list,
    all_bullpen_eras: dict,
    # Bonus inputs
    hit_streak: int = 0,
    multi_hit_last_10: int = 0,
    hr_last_3: int = 0,
    career_avg_at_park: float | None = None,
    park_favors_hand: bool = False,
    pitcher_era_last_3: float | None = None,
) -> dict:
    year = datetime.now().year

    # Fetch player-specific data
    season_stats = next((p for p in all_season if p["player_id"] == player_id), None)
    ten_day_stats = next((p for p in all_10day if p["player_id"] == player_id), None)
    splits = fetch_splits(player_id, year)
    h2h = fetch_h2h(player_id, pitcher_id)

    # Fallback if player not in 10-day list (e.g. hasn't played recently)
    if not ten_day_stats:
        ten_day_stats = {"avg": 0.0, "ops": 0.0}

    if not season_stats:
        season_stats = {"avg": 0.0, "ops": 0.0}

    temp_f = weather.get("temp_f", 72)
    wind_speed = weather.get("wind_speed", 0)
    wind_direction = weather.get("wind_direction", "calm")

    # Core scores
    core = {
        "ten_day":      score_10day_stats(ten_day_stats, all_10day),
        "season":       score_season_stats(season_stats, all_season),
        "season_hr": score_season_hr_rate(season_stats, all_season),
        "h2h":          score_h2h(h2h, all_h2h_ops),
        "lr_splits":    score_lr_splits(splits, pitcher_hand, all_split_ops),
        "park_factor":  score_park_factor(venue, batter_hand),
        "weather":      score_weather(temp_f, wind_speed, wind_direction),
        "bullpen":      score_bullpen(opp_team_id, all_bullpen_eras),
    }
    core_total = round(sum(core.values()), 2)

    # Bonus scores
    bonuses = score_bonuses(
        hit_streak=hit_streak,
        multi_hit_last_10=multi_hit_last_10,
        hr_last_3=hr_last_3,
        temp_f=temp_f,
        wind_speed=wind_speed,
        wind_direction=wind_direction,
        career_avg_at_park=career_avg_at_park,
        park_favors_hand=park_favors_hand,
        pitcher_era_last_3=pitcher_era_last_3,
        h2h_ab=h2h.get("pa", 0),
        h2h_avg=h2h.get("avg", 0.0),
    )

    return {
        "player_id": player_id,
        "core_score": core_total,
        "bonus_score": bonuses["total"],
        "total_score": round(core_total + bonuses["total"], 2),
        "max_core": 188,
        "breakdown": {
            "core": core,
            "bonuses": bonuses,
        },
        "h2h_note": "Defaulted to 50th percentile (< 6 PA)" if h2h["pa"] < 6 else None,
    }


def fetch_game_logs_for_date(date_str: str) -> dict:
    schedule_url = f"{MLB_API_BASE}/schedule"
    params = {"sportId": 1, "date": date_str}
    res = requests.get(schedule_url, params=params, timeout=15)
    res.raise_for_status()
    data = res.json()

    game_pks = []
    for date in data.get("dates", []):
        for game in date.get("games", []):
            game_pks.append(game["gamePk"])

    if not game_pks:
        return {}

    player_results = {}

    def fetch_boxscore(game_pk):
        box_url = f"{MLB_API_BASE}/game/{game_pk}/boxscore"
        box_res = requests.get(box_url, timeout=15)
        box_res.raise_for_status()
        return box_res.json()

    # Fetch all boxscores concurrently
    with ThreadPoolExecutor(max_workers=15) as executor:
        futures = {
            executor.submit(fetch_boxscore, pk): pk
            for pk in game_pks
        }
        for future in as_completed(futures):
            try:
                boxscore = future.result()
                teams = boxscore.get("teams", {})
                for side in ["home", "away"]:
                    players = teams.get(side, {}).get("players", {})
                    for key, player_data in players.items():
                        pid = player_data.get("person", {}).get("id")
                        stats = player_data.get(
                            "stats", {}
                        ).get("batting", {})
                        if not pid or not stats:
                            continue
                        ab = int(stats.get("atBats", 0) or 0)
                        if ab == 0:
                            continue
                        player_results[pid] = {
                            "hits": int(stats.get("hits", 0) or 0),
                            "hr": int(stats.get("homeRuns", 0) or 0),
                            "ab": ab,
                        }
            except Exception:
                continue

    return player_results

def fetch_scores_for_date(date_str: str, all_season: list,
                           all_10day_cache: dict,
                           all_bullpen_eras: dict) -> list:
    url = f"{MLB_API_BASE}/schedule"
    params = {
        "sportId": 1,
        "date": date_str,
        "hydrate": "probablePitcher,venue,team",
    }
    res = requests.get(url, params=params, timeout=15)
    res.raise_for_status()
    data = res.json()

    all_h2h_ops = [p["ops"] for p in all_season]
    all_split_ops = [{"avg": p["avg"], "ops": p["ops"]} for p in all_season]
    year = int(date_str[:4])

    # Build list of all batter/pitcher pairs for this day
    batter_game_info = []
    for date in data.get("dates", []):
        for game in date.get("games", []):
            venue = game.get("venue", {}).get("name", "Unknown")
            home = game["teams"]["home"]
            away = game["teams"]["away"]
            home_pitcher = home.get("probablePitcher")
            away_pitcher = away.get("probablePitcher")

            for side, pitcher, opp_team_id in [
                ("away", home_pitcher, home["team"]["id"]),
                ("home", away_pitcher, away["team"]["id"]),
            ]:
                if not pitcher:
                    continue
                pitcher_id = pitcher["id"]
                pitcher_hand = pitcher.get("pitchHand", {}).get("code", "R")
                team_id = home["team"]["id"] if side == "home" \
                          else away["team"]["id"]
                batters = [
                    p for p in all_season if p["team_id"] == team_id
                ][:9]

                for batter in batters:
                    batter_game_info.append({
                        "player_id": batter["player_id"],
                        "pitcher_id": pitcher_id,
                        "pitcher_hand": pitcher_hand,
                        "opp_team_id": opp_team_id,
                        "venue": venue,
                        "batter": batter,
                        "side": side,
                    })

    if not batter_game_info:
        return []

    # Fetch all H2H and splits concurrently
    print(f"  Fetching {len(batter_game_info)} player/pitcher pairs concurrently...")
    player_data = fetch_h2h_and_splits_batch(batter_game_info, year)

    # Score each player
    scored_players = []
    for info in batter_game_info:
        try:
            pid = info["player_id"]
            batter = info["batter"]
            batter_hand = batter.get("bats", "R")
            if batter_hand == "S":
                batter_hand = "L" if info["pitcher_hand"] == "R" else "R"

            ten_day = all_10day_cache.get(pid, {"avg": 0.0, "ops": 0.0})
            pdata = player_data.get(pid, {})
            h2h = pdata.get("h2h", {"avg": 0.0, "ops": 0.0, "pa": 0})
            splits = pdata.get("splits", {
                "vs_lhp": {"avg": 0.0, "ops": 0.0},
                "vs_rhp": {"avg": 0.0, "ops": 0.0},
            })

            core = {
                "ten_day": score_10day_stats(
                    ten_day, list(all_10day_cache.values())
                ),
                "season": score_season_stats(batter, all_season),
                "h2h": score_h2h(h2h),
                "lr_splits": score_lr_splits(
                    splits, info["pitcher_hand"], all_split_ops
                ),
                "park_factor": score_park_factor(info["venue"], batter_hand),
                "weather": score_weather(72, 0, "calm"),
                "bullpen": score_bullpen(
                    info["opp_team_id"], all_bullpen_eras
                ),
            }
            core_total = round(sum(core.values()), 2)
            scored_players.append({
                "player_id": pid,
                "name": batter["name"],
                "total_score": core_total,
            })
        except Exception:
            continue

    scored_players.sort(key=lambda x: x["total_score"], reverse=True)
    return scored_players

def fetch_h2h_and_splits_batch(
    player_pitcher_pairs: list,
    year: int,
    max_workers: int = 20
) -> dict:
    """
    Fetch H2H and splits for multiple players concurrently.
    player_pitcher_pairs: list of {player_id, pitcher_id}
    Returns {player_id: {h2h, splits}}
    """
    results = {}

    def fetch_one(pair):
        pid = pair["player_id"]
        pitcher_id = pair["pitcher_id"]
        try:
            h2h = fetch_h2h(pid, pitcher_id)
        except Exception:
            h2h = {"avg": 0.0, "ops": 0.0, "pa": 0}
        try:
            splits = fetch_splits(pid, year)
        except Exception:
            splits = {
                "vs_lhp": {"avg": 0.0, "ops": 0.0},
                "vs_rhp": {"avg": 0.0, "ops": 0.0},
            }
        return pid, {"h2h": h2h, "splits": splits}

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(fetch_one, pair): pair
            for pair in player_pitcher_pairs
        }
        for future in as_completed(futures):
            try:
                pid, data = future.result()
                results[pid] = data
            except Exception:
                continue

    return results


def score_season_hr_rate(player_season: dict, all_season: list) -> float:
    """
    Score based on season HR rate (HR per PA) — 28 points max.
    Percentile vs all qualified hitters this season.
    """
    pa = player_season.get("pa", 0)
    hr = player_season.get("hr", 0)

    if pa < 50:
        return 14.0  # 50th percentile default for unqualified players

    player_hr_rate = hr / pa
    all_hr_rates = []

    for p in all_season:
        p_pa = p.get("pa", 0)
        p_hr = p.get("hr", 0)
        if p_pa >= 50:
            all_hr_rates.append(p_hr / p_pa)

    if not all_hr_rates:
        return 14.0

    return percentile_score(player_hr_rate, all_hr_rates, 28)


def fetch_todays_lineups() -> dict:
    """
    Fetch confirmed lineups for today's games using the live game feed.
    Returns {team_id: [player_id, ...]} for teams whose lineups are confirmed.
    Works both pre-game (when lineups are posted) and during live games.
    """
    today = datetime.now().strftime("%Y-%m-%d")

    # Step 1 — get today's game PKs
    schedule_url = f"{MLB_API_BASE}/schedule"
    params = {"sportId": 1, "date": today}
    res = requests.get(schedule_url, params=params, timeout=15)
    res.raise_for_status()
    data = res.json()

    game_pks = []
    for date in data.get("dates", []):
        for game in date.get("games", []):
            game_pks.append(game["gamePk"])

    if not game_pks:
        return {}

    lineups = {}

    def fetch_game_lineup(game_pk):
        """Fetch lineup from live game feed for one game."""
        url = f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"
        res = requests.get(url, timeout=15)
        res.raise_for_status()
        data = res.json()

        game_data = data.get("gameData", {})
        live_data = data.get("liveData", {})
        boxscore = live_data.get("boxscore", {})
        teams = boxscore.get("teams", {})

        result = {}
        for side in ["home", "away"]:
            team_info = game_data.get("teams", {}).get(side, {})
            team_id = team_info.get("id")
            if not team_id:
                continue

            players = teams.get(side, {}).get("players", {})
            batting_order = []
            for key, player_data in players.items():
                # Only include players in the batting order
                order = player_data.get("battingOrder")
                if order:
                    pid = player_data.get("person", {}).get("id")
                    if pid:
                        batting_order.append((int(order), pid))

            if batting_order:
                # Sort by batting order position
                batting_order.sort(key=lambda x: x[0])
                result[team_id] = [pid for _, pid in batting_order]

        return result

    # Fetch all game lineups concurrently
    with ThreadPoolExecutor(max_workers=15) as executor:
        futures = {
            executor.submit(fetch_game_lineup, pk): pk
            for pk in game_pks
        }
        for future in as_completed(futures):
            try:
                result = future.result()
                lineups.update(result)
            except Exception:
                continue

    return lineups

def fetch_recent_game_appearances(player_id: int, days: int = 3) -> int:
    """
    Returns the number of games a player appeared in
    over the last N days. Used to filter out injured
    or resting players when lineup isn't posted yet.
    """
    end = datetime.now()
    start = end - timedelta(days=days)
    url = f"{MLB_API_BASE}/stats"
    params = {
        "stats": "byDateRange",
        "group": "hitting",
        "season": end.year,
        "startDate": start.strftime("%Y-%m-%d"),
        "endDate": end.strftime("%Y-%m-%d"),
        "playerId": player_id,
        "sportId": 1,
    }
    res = requests.get(url, params=params, timeout=10)
    res.raise_for_status()
    splits = res.json().get("stats", [{}])[0].get("splits", [])
    if not splits:
        return 0
    return int(splits[0]["stat"].get("gamesPlayed", 0) or 0)


def fetch_recent_appearances_batch(
    player_ids: list,
    days: int = 3,
    max_workers: int = 20
) -> dict:
    """
    Fetch recent game appearances for multiple players concurrently.
    Returns {player_id: games_played}
    """
    results = {}

    def fetch_one(pid):
        return pid, fetch_recent_game_appearances(pid, days)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(fetch_one, pid): pid
            for pid in player_ids
        }
        for future in as_completed(futures):
            try:
                pid, games = future.result()
                results[pid] = games
            except Exception:
                results[pid] = 0

    return results


# In-memory cache for Statcast batter data
# Persists for the lifetime of the server process
_statcast_batter_cache: dict = {}


def get_statcast_batter_cached(batter_id: int) -> "pd.DataFrame":
    if batter_id in _statcast_batter_cache:
        print(f"Cache hit for batter {batter_id}")
        return _statcast_batter_cache[batter_id]

    from pybaseball import statcast_batter
    start = "2015-01-01"
    end = datetime.now().strftime("%Y-%m-%d")

    print(f"Cache miss — fetching Statcast for batter {batter_id}...")
    df = statcast_batter(start, end, player_id=batter_id)

    if df is None:
        df = pd.DataFrame()

    # Filter out spring training at the cache level
    if not df.empty and "game_type" in df.columns:
        df = df[df["game_type"] != "S"]
        print(f"Filtered to {len(df)} regular/postseason rows")

    _statcast_batter_cache[batter_id] = df
    save_cache_to_disk()
    print(f"Cached {len(df)} rows for batter {batter_id}")
    return df