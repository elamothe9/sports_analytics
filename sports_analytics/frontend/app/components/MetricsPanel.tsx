import type { PlayerCardData } from "../lib/api"

const CORE_MAX: Record<string, { label: string; max: number }> = {
  ten_day: { label: "Last 10 days", max: 50 },
  season: { label: "Season AVG/OPS", max: 24 },
  season_hr: { label: "Season HR rate", max: 28 },
  h2h: { label: "Vs. pitcher (H2H)", max: 40 },
  lr_splits: { label: "L/R splits", max: 28 },
  park_factor: { label: "Park factor", max: 18 },
  weather: { label: "Weather", max: 14 },
  bullpen: { label: "Opp. bullpen", max: 14 },
}

function fmt(value: number | null | undefined, digits = 3): string {
  if (value === null || value === undefined) return "—"
  return value.toFixed(digits)
}

export default function MetricsPanel({ card }: { card: PlayerCardData }) {
  const today = card.today
  const pitcherHand = today?.pitcher.hand

  return (
    <div className="space-y-4 text-sm">
      <div className="grid grid-cols-2 gap-3">
        <div className="bg-gray-50 rounded-lg p-3">
          <p className="text-[10px] font-medium text-gray-400 uppercase tracking-wider mb-1.5">
            Last 10 days
          </p>
          {card.last_10 ? (
            <div className="flex gap-4">
              <span className="text-gray-700">
                AVG <span className="font-semibold">{fmt(card.last_10.avg)}</span>
              </span>
              <span className="text-gray-700">
                OPS <span className="font-semibold">{fmt(card.last_10.ops)}</span>
              </span>
            </div>
          ) : (
            <p className="text-gray-400 text-xs">Not enough recent at-bats</p>
          )}
        </div>

        <div className="bg-gray-50 rounded-lg p-3">
          <p className="text-[10px] font-medium text-gray-400 uppercase tracking-wider mb-1.5">
            Season
          </p>
          <div className="flex gap-4 flex-wrap">
            <span className="text-gray-700">
              AVG <span className="font-semibold">{fmt(card.season.avg)}</span>
            </span>
            <span className="text-gray-700">
              OPS <span className="font-semibold">{fmt(card.season.ops)}</span>
            </span>
            <span className="text-gray-700">
              HR <span className="font-semibold">{card.season.hr}</span>
            </span>
          </div>
        </div>
      </div>

      {card.splits && (
        <div className="bg-gray-50 rounded-lg p-3">
          <p className="text-[10px] font-medium text-gray-400 uppercase tracking-wider mb-1.5">
            Splits
          </p>
          <div className="grid grid-cols-2 gap-3">
            <div
              className={
                pitcherHand === "L"
                  ? "rounded-md bg-emerald-50 border border-emerald-100 px-2 py-1.5"
                  : "px-2 py-1.5"
              }
            >
              <p className="text-xs text-gray-400 mb-0.5">
                vs LHP {pitcherHand === "L" && "· today"}
              </p>
              <p className="text-gray-700">
                AVG <span className="font-semibold">{fmt(card.splits.vs_lhp.avg)}</span>
                {"  ·  "}
                OPS <span className="font-semibold">{fmt(card.splits.vs_lhp.ops)}</span>
              </p>
            </div>
            <div
              className={
                pitcherHand === "R"
                  ? "rounded-md bg-emerald-50 border border-emerald-100 px-2 py-1.5"
                  : "px-2 py-1.5"
              }
            >
              <p className="text-xs text-gray-400 mb-0.5">
                vs RHP {pitcherHand === "R" && "· today"}
              </p>
              <p className="text-gray-700">
                AVG <span className="font-semibold">{fmt(card.splits.vs_rhp.avg)}</span>
                {"  ·  "}
                OPS <span className="font-semibold">{fmt(card.splits.vs_rhp.ops)}</span>
              </p>
            </div>
          </div>
        </div>
      )}

      {today ? (
        <div className="bg-gray-50 rounded-lg p-3 space-y-3">
          <div className="flex items-center justify-between">
            <p className="text-[10px] font-medium text-gray-400 uppercase tracking-wider">
              Today · vs {today.pitcher.name ?? "TBD"} ({today.pitcher.hand}HP)
              {" · "}
              {today.venue}
            </p>
            <span className="text-xs font-semibold text-emerald-700 bg-emerald-50 rounded-full px-2 py-0.5">
              {today.total_score.toFixed(1)} pts
            </span>
          </div>

          <div>
            <p className="text-xs text-gray-500 mb-1">
              Career vs. this pitcher:{" "}
              {today.h2h.pa > 0 ? (
                <span className="font-medium text-gray-700">
                  {fmt(today.h2h.avg)} AVG · {fmt(today.h2h.ops)} OPS ·{" "}
                  {today.h2h.pa} PA
                </span>
              ) : (
                <span className="text-gray-400">no history</span>
              )}
            </p>
            {today.h2h_note && (
              <p className="text-[11px] text-amber-600">{today.h2h_note}</p>
            )}
          </div>

          <div className="space-y-1.5">
            {Object.entries(CORE_MAX).map(([key, meta]) => {
              const value = today.breakdown.core[key as keyof typeof today.breakdown.core]
              if (value === undefined) return null
              const pct = Math.max(0, Math.min(100, (value / meta.max) * 100))
              return (
                <div key={key} className="flex items-center gap-2">
                  <span className="w-32 shrink-0 text-[11px] text-gray-400">
                    {meta.label}
                  </span>
                  <div className="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-emerald-500 rounded-full"
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                  <span className="w-14 shrink-0 text-right text-[11px] text-gray-500">
                    {value.toFixed(1)}/{meta.max}
                  </span>
                </div>
              )
            })}
          </div>
        </div>
      ) : (
        <p className="text-xs text-gray-400 bg-gray-50 rounded-lg p-3">
          No projected matchup for this player today.
        </p>
      )}
    </div>
  )
}
