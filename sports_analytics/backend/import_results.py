"""
import_results.py
─────────────────
Fill in the result columns of the props tracker automatically.

For every logged row (a date + player) that still has a blank result, this
pulls the player's actual box-score line for that date from the MLB Stats API
and writes 1/0 into the four prop columns:

    HR  (col I)  -> 1 if the player hit >= 1 home run
    2H  (col J)  -> 1 if the player had  >= 2 hits
    3H  (col K)  -> 1 if the player had  >= 3 hits
    1H  (col W)  -> 1 if the player had  >= 1 hit

Odds columns are never touched — enter those by hand. Existing (already
filled) results are preserved; only blank cells are filled. A player who did
not come to the plate that day (DNP / scratched) is left blank so you can
void the bet yourself.

Usage:
    python import_results.py                # fill blanks for all past dates
    python import_results.py --overwrite    # also recompute already-filled cells
    python import_results.py --date 2026-08-24   # just this one date

Requires:  pip install requests openpyxl
Note: close the workbook in Excel before running (Excel locks the file).
"""

import os
import unicodedata
import argparse
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
import openpyxl

# ── CONFIG ────────────────────────────────────────────────────
# The live tracker lives in the repo root (one level up from backend/).
# Resolved relative to this file so it works from any working directory.
TRACKER_PATH = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tk.xlsx")
)
SHEET_NAME   = "Props Tracker"
MLB_API_BASE = "https://statsapi.mlb.com/api/v1"
DATA_START_ROW = 5

# 1-based column indexes in the Props Tracker sheet
COL_DATE, COL_PLAYER, COL_TEAM = 1, 2, 3
COL_HR, COL_2H, COL_3H = 9, 10, 11     # I, J, K
COL_1H = 23                             # W
RESULT_COLS = {"HR": COL_HR, "2H": COL_2H, "3H": COL_3H, "1H": COL_1H}


# ── HELPERS ───────────────────────────────────────────────────
def norm_name(s: str) -> str:
    """Lowercase, strip accents and periods — for robust name matching."""
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.casefold().replace(".", "").strip()


def is_blank(v) -> bool:
    return v is None or (isinstance(v, str) and v.strip() == "")


def fetch_team_abbr_map() -> dict:
    """{team_id: 'HOU'} for disambiguating players with the same name."""
    try:
        r = requests.get(f"{MLB_API_BASE}/teams", params={"sportId": 1}, timeout=15)
        r.raise_for_status()
        return {t["id"]: t.get("abbreviation", "") for t in r.json().get("teams", [])}
    except Exception:
        return {}


def fetch_results_for_date(date_str: str, abbr_map: dict) -> dict:
    """
    Return {normalized_name: [(team_abbr, hits, hr), ...]} for every batter who
    came to the plate that date. A name can map to more than one entry only if
    two players share a name on the slate — team disambiguates.
    """
    r = requests.get(
        f"{MLB_API_BASE}/schedule",
        params={"sportId": 1, "date": date_str},
        timeout=15,
    )
    r.raise_for_status()
    game_pks = [
        g["gamePk"]
        for d in r.json().get("dates", [])
        for g in d.get("games", [])
    ]
    if not game_pks:
        return {}

    out = {}

    def fetch_box(pk):
        b = requests.get(f"{MLB_API_BASE}/game/{pk}/boxscore", timeout=15)
        b.raise_for_status()
        return b.json()

    with ThreadPoolExecutor(max_workers=10) as ex:
        futures = [ex.submit(fetch_box, pk) for pk in game_pks]
        for fut in as_completed(futures):
            try:
                box = fut.result()
            except Exception:
                continue
            for side in ("home", "away"):
                team = box.get("teams", {}).get(side, {})
                team_abbr = abbr_map.get(team.get("team", {}).get("id"), "")
                for pdata in team.get("players", {}).values():
                    name = pdata.get("person", {}).get("fullName")
                    bat = pdata.get("stats", {}).get("batting", {})
                    if not name or not bat:
                        continue
                    pa = int(bat.get("plateAppearances", 0) or 0)
                    ab = int(bat.get("atBats", 0) or 0)
                    if pa == 0 and ab == 0:
                        continue  # did not come to the plate — leave blank
                    hits = int(bat.get("hits", 0) or 0)
                    hr = int(bat.get("homeRuns", 0) or 0)
                    out.setdefault(norm_name(name), []).append(
                        (str(team_abbr).upper(), hits, hr)
                    )
    return out


def prop_results(hits: int, hr: int) -> dict:
    """1/0 for each prop from a player's hit / HR line."""
    return {
        "HR": 1 if hr >= 1 else 0,
        "1H": 1 if hits >= 1 else 0,
        "2H": 1 if hits >= 2 else 0,
        "3H": 1 if hits >= 3 else 0,
    }


def match_line(candidates: list, sheet_team: str):
    """Pick the right (hits, hr) for a row given same-name candidates."""
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0][1], candidates[0][2]
    want = str(sheet_team or "").upper()
    for abbr, hits, hr in candidates:
        if abbr == want:
            return hits, hr
    return candidates[0][1], candidates[0][2]  # fall back, ambiguous


# ── MAIN ──────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--overwrite", action="store_true",
                    help="recompute cells that already have a result")
    ap.add_argument("--date", help="only process this date (YYYY-MM-DD)")
    ap.add_argument("--path", default=TRACKER_PATH, help="tracker file path")
    args = ap.parse_args()

    today = datetime.now().date()

    try:
        wb = openpyxl.load_workbook(args.path)
    except PermissionError:
        print(f"ERROR: can't open {args.path} — is it open in Excel? Close it and retry.")
        return
    except FileNotFoundError:
        print(f"ERROR: {args.path} not found. Run this from the folder that holds it.")
        return
    ws = wb[SHEET_NAME]

    # Gather rows that need results, grouped by date.
    rows_by_date = {}
    for r in range(DATA_START_ROW, ws.max_row + 1):
        player = ws.cell(r, COL_PLAYER).value
        date_val = ws.cell(r, COL_DATE).value
        if is_blank(player) or is_blank(date_val):
            continue
        d = date_val.date() if hasattr(date_val, "date") else \
            datetime.strptime(str(date_val)[:10], "%Y-%m-%d").date()
        if args.date and d.isoformat() != args.date:
            continue
        if d >= today:
            continue  # today / future — games not final yet
        needs = args.overwrite or any(
            is_blank(ws.cell(r, c).value) for c in RESULT_COLS.values()
        )
        if needs:
            rows_by_date.setdefault(d.isoformat(), []).append(r)

    if not rows_by_date:
        print("Nothing to fill — every past row already has results.")
        return

    abbr_map = fetch_team_abbr_map()
    filled_rows = 0
    filled_cells = 0
    not_found = []

    for date_str in sorted(rows_by_date):
        rows = rows_by_date[date_str]
        print(f"{date_str}: {len(rows)} row(s) to fill — fetching box scores...")
        try:
            results = fetch_results_for_date(date_str, abbr_map)
        except Exception as e:
            print(f"  ERROR fetching {date_str}: {e}")
            continue

        for r in rows:
            name = ws.cell(r, COL_PLAYER).value
            team = ws.cell(r, COL_TEAM).value
            cands = results.get(norm_name(name))
            line = match_line(cands, team) if cands else None
            if line is None:
                not_found.append(f"{date_str}  {name}")
                continue
            hits, hr = line
            res = prop_results(hits, hr)
            wrote_any = False
            for prop, col in RESULT_COLS.items():
                if args.overwrite or is_blank(ws.cell(r, col).value):
                    ws.cell(r, col).value = res[prop]
                    filled_cells += 1
                    wrote_any = True
            if wrote_any:
                filled_rows += 1

    wb.save(args.path)
    print(f"\n✓ Filled {filled_cells} result cell(s) across {filled_rows} player-day(s).")
    if not_found:
        print(f"\n{len(not_found)} player-day(s) had no box-score line "
              f"(did not play / name mismatch) — left blank:")
        for x in not_found:
            print(f"   {x}")
    print("\nOpen the tracker in Excel to let P&L and the Summary recalculate.")


if __name__ == "__main__":
    main()
