"use client"

import { useEffect, useState } from "react"
import { fetchScoreboard, type ScoreboardGame } from "../lib/api"

function inningLabel(g: ScoreboardGame): string {
  if (!g.inning) return ""
  const st = (g.inning_state || "").toLowerCase()
  if (st.startsWith("top")) return `▲ ${g.inning}`
  if (st.startsWith("bot")) return `▼ ${g.inning}`
  if (st.startsWith("mid")) return `Mid ${g.inning}`
  if (st.startsWith("end")) return `End ${g.inning}`
  return `${g.inning}`
}

export default function LiveScoreboard() {
  const [games, setGames] = useState<ScoreboardGame[] | null>(null)

  useEffect(() => {
    let alive = true
    const load = () =>
      fetchScoreboard()
        .then((r) => {
          if (alive) setGames(r.games)
        })
        .catch(() => {})
    load()
    // Live scores move fast — refresh every 60s, independent of the board.
    const id = setInterval(load, 60_000)
    return () => {
      alive = false
      clearInterval(id)
    }
  }, [])

  const live = (games ?? []).filter((g) => g.abstract_state === "Live")
  if (live.length === 0) return null

  return (
    <div className="mb-4 bg-white border border-gray-100 rounded-xl px-4 py-3">
      <div className="flex items-center gap-2 mb-2">
        <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse" />
        <span className="text-[10px] font-semibold text-red-600 uppercase tracking-wider">
          Live now
        </span>
        <span className="text-[10px] text-gray-300">
          {live.length} game{live.length > 1 ? "s" : ""} in progress
        </span>
      </div>
      <div className="flex gap-2 overflow-x-auto pb-1">
        {live.map((g) => (
          <div
            key={`${g.game_id}-${g.game_number}`}
            className="shrink-0 flex items-center gap-2.5 rounded-lg bg-gray-50 border border-gray-100 px-3 py-1.5 text-xs tabular-nums"
          >
            <span className="text-gray-600">
              {g.away_abbr ?? g.away_name}{" "}
              <span className="font-semibold text-gray-900">
                {g.away_runs ?? 0}
              </span>
            </span>
            <span className="text-gray-300">@</span>
            <span className="text-gray-600">
              <span className="font-semibold text-gray-900">
                {g.home_runs ?? 0}
              </span>{" "}
              {g.home_abbr ?? g.home_name}
            </span>
            <span className="text-[10px] font-medium text-emerald-700 bg-emerald-50 rounded px-1.5 py-0.5">
              {inningLabel(g)}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
