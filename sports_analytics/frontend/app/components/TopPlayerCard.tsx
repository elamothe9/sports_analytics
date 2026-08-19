"use client"

import { useState } from "react"
import Link from "next/link"
import { fetchPlayerCard, type PlayerCardData, type TopPlayer } from "../lib/api"
import MetricsPanel from "./MetricsPanel"

const MAX_CORE_SCORE = 188

export default function TopPlayerCard({
  player,
  rank,
}: {
  player: TopPlayer
  rank: number
}) {
  const [expanded, setExpanded] = useState(false)
  const [card, setCard] = useState<PlayerCardData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const score = player.total_score ?? player.pre_h2h_score
  const pct = Math.max(0, Math.min(100, (score / MAX_CORE_SCORE) * 100))

  async function toggle() {
    const next = !expanded
    setExpanded(next)
    if (next && !card && !loading) {
      setLoading(true)
      setError(null)
      try {
        setCard(await fetchPlayerCard(player.player_id))
      } catch {
        setError("Could not load player metrics.")
      } finally {
        setLoading(false)
      }
    }
  }

  return (
    <div className="bg-white border border-gray-100 rounded-xl p-4 hover:border-gray-300 transition-colors">
      <div className="flex items-center gap-3">
        <span className="w-8 h-8 shrink-0 rounded-full bg-gray-900 text-white text-xs font-semibold flex items-center justify-center">
          {rank}
        </span>

        <div className="min-w-0 flex-1">
          <Link
            href={`/player/${player.player_id}`}
            className="text-sm font-medium text-gray-900 hover:underline truncate block"
          >
            {player.name}
          </Link>
          <p className="text-xs text-gray-400 truncate">
            {player.team} · vs {player.pitcher_hand}HP · {player.venue}
          </p>
        </div>

        <div className="text-right shrink-0">
          <p className="text-lg font-semibold text-emerald-700">
            {score.toFixed(1)}
          </p>
          <p className="text-[10px] text-gray-300 uppercase tracking-wider">
            score
          </p>
        </div>
      </div>

      <div className="mt-3 h-1.5 bg-gray-100 rounded-full overflow-hidden">
        <div
          className="h-full bg-emerald-500 rounded-full"
          style={{ width: `${pct}%` }}
        />
      </div>

      <button
        type="button"
        onClick={toggle}
        className="mt-3 text-xs font-medium text-emerald-700 hover:text-emerald-900"
      >
        {expanded ? "Hide metrics ▲" : "Show metrics ▼"}
      </button>

      {expanded && (
        <div className="mt-3 border-t border-gray-50 pt-3">
          {loading && (
            <p className="text-xs text-gray-400">Loading metrics...</p>
          )}
          {error && <p className="text-xs text-red-500">{error}</p>}
          {card && <MetricsPanel card={card} />}
        </div>
      )}
    </div>
  )
}
