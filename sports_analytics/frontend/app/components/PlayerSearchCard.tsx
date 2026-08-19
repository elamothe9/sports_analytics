import Link from "next/link"
import type { PlayerCardData } from "../lib/api"
import MetricsPanel from "./MetricsPanel"

export default function PlayerSearchCard({ card }: { card: PlayerCardData }) {
  const initials = card.name
    .split(" ")
    .map((n) => n[0])
    .join("")
    .slice(0, 2)
    .toUpperCase()

  return (
    <div className="bg-white border border-gray-100 rounded-xl p-4">
      <div className="flex items-center gap-3 mb-4">
        <div className="w-10 h-10 shrink-0 rounded-full bg-emerald-50 text-emerald-800 flex items-center justify-center text-xs font-semibold">
          {initials}
        </div>
        <div className="min-w-0 flex-1">
          <Link
            href={`/player/${card.player_id}`}
            className="text-sm font-medium text-gray-900 hover:underline"
          >
            {card.name}
          </Link>
          <p className="text-xs text-gray-400">
            {card.team_name} · Bats {card.bats}
          </p>
        </div>
        {card.today ? (
          <div className="text-right shrink-0">
            <p className="text-lg font-semibold text-emerald-700">
              {card.today.total_score.toFixed(1)}
            </p>
            <p className="text-[10px] text-gray-300 uppercase tracking-wider">
              today&apos;s score
            </p>
          </div>
        ) : (
          <span className="text-[10px] text-gray-300 uppercase tracking-wider shrink-0">
            no game today
          </span>
        )}
      </div>

      <MetricsPanel card={card} />
    </div>
  )
}
