"use client"

import { useState } from "react"
import Link from "next/link"
import { fetchPlayerCard, type PlayerCardData, type TopPlayer } from "../lib/api"
import MetricsPanel from "./MetricsPanel"

const MAX_CORE_SCORE = 216

export default function TopPlayerCard({
  player,
  rank,
  scoreMin,
  scoreMax,
}: {
  player: TopPlayer
  rank: number
  // Lowest / highest score currently on the board. When provided, the bar
  // color is spread across this visible range rather than the full 0→max
  // scale, so closely-bunched top-25 scores still separate by color.
  scoreMin?: number
  scoreMax?: number
}) {
  const [expanded, setExpanded] = useState(false)
  const [card, setCard] = useState<PlayerCardData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const score = player.total_score ?? player.pre_h2h_score
  const pct = Math.max(0, Math.min(100, (score / MAX_CORE_SCORE) * 100))

  // Game timing / status for the card.
  const started = player.abstract_state === "Live"
  const finalGame = player.abstract_state === "Final"
  let gameTime: string | null = null
  if (player.game_date) {
    try {
      gameTime = new Date(player.game_date).toLocaleTimeString([], {
        hour: "numeric",
        minute: "2-digit",
      })
    } catch {
      gameTime = null
    }
  }

  // Color position (0 = red, 1 = green). Normalize to the visible score range
  // when we have it so the board's spread of scores uses the whole spectrum;
  // otherwise fall back to the absolute scale.
  const hasRange =
    scoreMin != null && scoreMax != null && scoreMax > scoreMin
  const colorT = hasRange
    ? Math.max(0, Math.min(1, (score - scoreMin!) / (scoreMax! - scoreMin!)))
    : pct / 100

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
          <div className="flex items-center gap-2 min-w-0">
            <Link
              href={`/player/${player.player_id}`}
              className="text-sm font-medium text-gray-900 hover:underline truncate"
            >
              {player.name}
            </Link>
            {player.doubleheader && (
              <span className="shrink-0 inline-flex items-center rounded-full bg-amber-50 border border-amber-200 text-amber-700 text-[9px] font-semibold px-1.5 py-px uppercase tracking-wide">
                Game {player.game_number}
              </span>
            )}
            {started && (
              <span className="shrink-0 inline-flex items-center gap-1 rounded-full bg-red-50 border border-red-200 text-red-600 text-[9px] font-semibold px-1.5 py-px uppercase tracking-wide">
                <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse" />
                Live
              </span>
            )}
            {finalGame && (
              <span className="shrink-0 inline-flex items-center rounded-full bg-gray-100 border border-gray-200 text-gray-500 text-[9px] font-semibold px-1.5 py-px uppercase tracking-wide">
                Final
              </span>
            )}
          </div>
          <p className="text-xs text-gray-400 truncate">
            {player.team} · vs{" "}
            {player.pitcher_name
              ? `${player.pitcher_name} (${player.pitcher_hand}HP)`
              : `${player.pitcher_hand}HP`}{" "}
            · {player.venue}
            {gameTime && !started && !finalGame && (
              <span className="text-gray-500"> · {gameTime}</span>
            )}
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
          className="h-full rounded-full"
          style={{
            width: `${pct}%`,
            // Red→amber→green spectrum. The bar reveals the slice of the
            // gradient up to its color position (colorT), so the lowest score on
            // the board reads red and the highest reads green — spreading the
            // full spectrum across whatever range of scores is showing.
            backgroundImage:
              "linear-gradient(to right, #ef4444, #f59e0b, #22c55e)",
            backgroundSize: `${colorT > 0 ? 100 / colorT : 100}% 100%`,
            backgroundRepeat: "no-repeat",
          }}
        />
      </div>

      {player.active_bonuses && player.active_bonuses.length > 0 && (
        <div className="mt-2.5 flex flex-wrap gap-1.5">
          {player.active_bonuses.map((b) => (
            <span
              key={b.key}
              className="inline-flex items-center gap-1 rounded-full bg-amber-50 border border-amber-200 text-amber-800 text-[10px] font-medium px-2 py-0.5"
            >
              {b.label}
              <span className="text-amber-500">+{b.points}</span>
            </span>
          ))}
        </div>
      )}

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
