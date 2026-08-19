"""
daily_props_tracker.py
─────────────────────
Run once per day before games start.

What it does:
  1. Calls the Analytic Overview backend to get today's top 15 players
  2. Appends a new row per player to the master Excel tracker
  3. Leaves odds and result columns blank for manual entry

Usage:
  python daily_props_tracker.py

Workflow:
  Morning — run this script, then open the Excel file and fill in
            odds from FanDuel/DraftKings for each player (~5 mins)
  Evening — fill in result columns after games (1=hit, 0=miss)
            P&L calculates automatically

Requirements:
  pip install requests openpyxl
"""

import os
import re
import requests
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from datetime import datetime

# ── CONFIG ────────────────────────────────────────────────────
BACKEND_URL  = "http://localhost:8000"
TRACKER_PATH = "analytic_overview_props_tracker.xlsx"
TOP_N        = 15
TODAY        = datetime.now().strftime("%Y-%m-%d")

# Styling constants — match the tracker file
RESULT_BG  = "FFF9E6"
ALT_BG     = "F7F9FC"
BORDER_CLR = "CCCCCC"
thin       = Side(style="thin", color=BORDER_CLR)
border     = Border(left=thin, right=thin, top=thin, bottom=thin)
body_font  = Font(name="Arial", size=10)


# ── STEP 1: GET TODAY'S TOP PLAYERS FROM BACKEND ─────────────
def get_top_players(n: int = TOP_N) -> list:
    """Call the fast scores endpoint and return the top N players."""
    print(f"Fetching top {n} players from backend...")
    try:
        res = requests.get(
            f"{BACKEND_URL}/api/scores/today/fast",
            timeout=120
        )
        res.raise_for_status()
        data = res.json()
        players = data.get("top_25", [])[:n]
        print(f"  Got {len(players)} players.")
        return players
    except Exception as e:
        print(f"  ERROR fetching players: {e}")
        return []


# ── STEP 2: APPEND TO EXCEL TRACKER ──────────────────────────
def append_to_tracker(players: list):
    """Append today's players to the master Excel tracker."""
    print(f"Opening tracker: {TRACKER_PATH}")

    if not os.path.exists(TRACKER_PATH):
        print(f"  ERROR: {TRACKER_PATH} not found.")
        print(
            "  Make sure analytic_overview_props_tracker.xlsx is "
            "in the same folder as this script."
        )
        return

    wb = openpyxl.load_workbook(TRACKER_PATH)
    ws = wb["Props Tracker"]

    # Find first empty row (data starts at row 5)
    first_empty = 5
    for row in ws.iter_rows(min_row=5, max_row=ws.max_row):
        if row[0].value is None:
            first_empty = row[0].row
            break
    else:
        first_empty = ws.max_row + 1

    # Check if today's data already exists — avoid duplicates
    for row in ws.iter_rows(min_row=5, max_row=ws.max_row, max_col=1):
        if row[0].value == TODAY:
            print(
                f"  WARNING: Data for {TODAY} already exists in "
                f"the tracker. Delete those rows first if you want "
                f"to re-run."
            )
            return

    print(
        f"  Appending {len(players)} rows starting at "
        f"row {first_empty}..."
    )

    for i, player in enumerate(players, 0):
        row_num = first_empty + i
        alt = (row_num % 2 == 0)
        bg = ALT_BG if alt else "FFFFFF"

        name    = player.get("name", "Unknown")
        team    = player.get("team", "")
        score   = round(player.get("total_score", 0), 1)

        # Try to get pitcher info from the breakdown
        pitcher = ""
        breakdown = player.get("breakdown", {})
        if not pitcher:
            pitcher = player.get("pitcher_name", "")

        def write(col, val, is_result=False):
            cell = ws[f"{col}{row_num}"]
            cell.value = val
            cell.font = body_font
            cell.border = border
            if is_result:
                cell.fill = PatternFill(
                    "solid", fgColor=RESULT_BG
                )
                cell.alignment = Alignment(
                    horizontal="center", vertical="center"
                )
            else:
                cell.fill = PatternFill("solid", fgColor=bg)
                cell.alignment = Alignment(
                    horizontal="center", vertical="center"
                ) if col not in ("A", "B", "E") else Alignment(
                    horizontal="left", vertical="center"
                )

        # Player info
        write("A", TODAY)
        write("B", name)
        write("C", team)
        write("D", score)
        write("E", pitcher)

        # Odds — left blank for manual entry
        write("F", "")   # HR odds
        write("G", "")   # 2H odds
        write("H", "")   # 3H odds

        # Results — left blank, filled in after games
        write("I", "", is_result=True)
        write("J", "", is_result=True)
        write("K", "", is_result=True)

        # P&L formulas — auto-calculate from odds and result
        r = row_num
        ws[f"L{r}"].value = (
            f'=IFERROR(IF(I{r}="","",IF(I{r}=1,'
            f'IF(F{r}>0,F{r}/100,100/ABS(F{r})),-1)),"")'
        )
        ws[f"M{r}"].value = (
            f'=IFERROR(IF(J{r}="","",IF(J{r}=1,'
            f'IF(G{r}>0,G{r}/100,100/ABS(G{r})),-1)),"")'
        )
        ws[f"N{r}"].value = (
            f'=IFERROR(IF(K{r}="","",IF(K{r}=1,'
            f'IF(H{r}>0,H{r}/100,100/ABS(H{r})),-1)),"")'
        )
        ws[f"O{r}"].value = (
            f'=IFERROR(IF(_xlfn.CONCAT(I{r},J{r},K{r})="","",'
            f'IFERROR(L{r},0)+IFERROR(M{r},0)+'
            f'IFERROR(N{r},0)),"")'
        )

        for col in ("L", "M", "N", "O"):
            ws[f"{col}{r}"].font = body_font
            ws[f"{col}{r}"].border = border
            ws[f"{col}{r}"].fill = PatternFill(
                "solid", fgColor=RESULT_BG
            )
            ws[f"{col}{r}"].alignment = Alignment(
                horizontal="center", vertical="center"
            )

        ws.row_dimensions[row_num].height = 17

    wb.save(TRACKER_PATH)
    print(f"  Saved {len(players)} rows to {TRACKER_PATH}")


# ── MAIN ──────────────────────────────────────────────────────
def main():
    print(f"\n{'='*55}")
    print(f"  Analytic Overview — Daily Props Tracker")
    print(f"  Date: {TODAY}")
    print(f"{'='*55}\n")

    # Get top players from backend
    players = get_top_players(TOP_N)
    if not players:
        print(
            "No players returned from backend. "
            "Make sure the backend is running on port 8000."
        )
        return

    print(f"\nTop {len(players)} players today:")
    for i, p in enumerate(players, 1):
        print(
            f"  {i:2}. {p.get('name', '?'):<22} "
            f"Score: {p.get('total_score', 0):.1f}"
        )

    # Write to tracker
    print(f"\nWriting to tracker...")
    append_to_tracker(players)

    print(f"\n✓ Done. Next steps:")
    print(f"  1. Open {TRACKER_PATH}")
    print(f"  2. Fill in odds columns F, G, H from FanDuel/DraftKings")
    print(f"     F = HR odds (e.g. +550)")
    print(f"     G = 2+ hits odds (e.g. +210)")
    print(f"     H = 3+ hits odds (e.g. +950)")
    print(f"  3. After games, fill in result columns I, J, K")
    print(f"     1 = hit the prop, 0 = missed")
    print(f"  4. P&L calculates automatically\n")


if __name__ == "__main__":
    main()