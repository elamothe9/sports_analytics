from fastapi import APIRouter, HTTPException
from services.scoring import (
    fetch_all_season_stats,
    fetch_all_10day_stats,
    fetch_bullpen_eras,
    fetch_game_logs_for_date,
    fetch_scores_for_date,
)
from datetime import datetime, timedelta

router = APIRouter()


@router.get("/validation/backtest")
def backtest(days: int = 15, top_n: int = 25):
    """
    Run backtesting validation over the last N days.
    For each day, scores all players, takes the top N,
    then checks their actual game results.
    Returns hit rate statistics.
    """
    try:
        year = datetime.now().year
        print(f"Fetching season and bullpen data...")
        all_season = fetch_all_season_stats(year)
        all_bullpen_eras = fetch_bullpen_eras(year)

        # Build 10-day cache as a dict for fast lookup
        all_10day_list = fetch_all_10day_stats(year)
        all_10day_cache = {p["player_id"]: p for p in all_10day_list}

        daily_results = []
        total_players_evaluated = 0

        # Counters across all days
        counters = {
            "at_least_1_hit": 0,
            "at_least_2_hits": 0,
            "at_least_3_hits": 0,
            "at_least_1_hr": 0,
            "total": 0,
        }

        for i in range(1, days + 1):
            date = datetime.now() - timedelta(days=i)

            # Skip today and future dates
            if date.date() >= datetime.now().date():
                continue

            date_str = date.strftime("%Y-%m-%d")
            print(f"Processing {date_str}...")

            try:
                # Get scores for this date
                scored = fetch_scores_for_date(
                    date_str,
                    all_season,
                    all_10day_cache,
                    all_bullpen_eras,
                )
                top_players = scored[:top_n]

                if not top_players:
                    continue

                # Get actual results for this date
                actual = fetch_game_logs_for_date(date_str)

                day_counters = {
                    "at_least_1_hit": 0,
                    "at_least_2_hits": 0,
                    "at_least_3_hits": 0,
                    "at_least_1_hr": 0,
                    "scored": 0,
                    "no_result": 0,
                }

                for player in top_players:
                    pid = player["player_id"]
                    result = actual.get(pid)

                    if not result:
                        day_counters["no_result"] += 1
                        continue

                    day_counters["scored"] += 1
                    hits = result["hits"]
                    hr = result["hr"]

                    if hits >= 1:
                        day_counters["at_least_1_hit"] += 1
                        counters["at_least_1_hit"] += 1
                    if hits >= 2:
                        day_counters["at_least_2_hits"] += 1
                        counters["at_least_2_hits"] += 1
                    if hits >= 3:
                        day_counters["at_least_3_hits"] += 1
                        counters["at_least_3_hits"] += 1
                    if hr >= 1:
                        day_counters["at_least_1_hr"] += 1
                        counters["at_least_1_hr"] += 1

                    counters["total"] += 1
                    total_players_evaluated += 1

                # Daily hit rates
                scored_count = day_counters["scored"]
                daily_results.append({
                    "date": date_str,
                    "top_players_scored": len(top_players),
                    "results_found": scored_count,
                    "no_game_result": day_counters["no_result"],
                    "hit_rates": {
                        "1_hit_pct": round(
                            day_counters["at_least_1_hit"] /
                            scored_count * 100, 1
                        ) if scored_count else None,
                        "2_hit_pct": round(
                            day_counters["at_least_2_hits"] /
                            scored_count * 100, 1
                        ) if scored_count else None,
                        "3_hit_pct": round(
                            day_counters["at_least_3_hits"] /
                            scored_count * 100, 1
                        ) if scored_count else None,
                        "hr_pct": round(
                            day_counters["at_least_1_hr"] /
                            scored_count * 100, 1
                        ) if scored_count else None,
                    }
                })

            except Exception as e:
                daily_results.append({
                    "date": date_str,
                    "error": str(e)
                })
                continue

        # Overall aggregated hit rates
        total = counters["total"]
        overall = {
            "total_player_days_evaluated": total,
            "days_processed": len(daily_results),
            "top_n": top_n,
            "at_least_1_hit_pct": round(
                counters["at_least_1_hit"] / total * 100, 1
            ) if total else None,
            "at_least_2_hits_pct": round(
                counters["at_least_2_hits"] / total * 100, 1
            ) if total else None,
            "at_least_3_hits_pct": round(
                counters["at_least_3_hits"] / total * 100, 1
            ) if total else None,
            "at_least_1_hr_pct": round(
                counters["at_least_1_hr"] / total * 100, 1
            ) if total else None,
        }

        return {
            "summary": overall,
            "daily_breakdown": daily_results,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


