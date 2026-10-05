"use client"

import { Fragment, useState } from "react"
import Link from "next/link"
import type { MatchupRanking } from "../lib/api"

export default function MatchupRankingsTable({
  rankings,
}: {
  rankings: MatchupRanking[]
}) {
  const [open, setOpen] = useState<Set<string>>(new Set())

  if (rankings.length === 0) {
    return (
      <p className="text-sm text-gray-400 bg-white border border-gray-100 rounded-xl p-6 text-center">
        No matchup rankings available — check back once today&apos;s slate is posted.
      </p>
    )
  }

  const maxScore = Math.max(...rankings.map((m) => m.combined_avg), 1)

  function keyFor(m: MatchupRanking) {
    return `${m.matchup}-${m.game_number}`
  }

  function toggle(k: string) {
    setOpen((prev) => {
      const next = new Set(prev)
      if (next.has(k)) next.delete(k)
      else next.add(k)
      return next
    })
  }

  return (
    <div className="bg-white border border-gray-100 rounded-xl overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-[10px] text-gray-400 uppercase tracking-wider border-b border-gray-100">
            <th className="px-4 py-3 font-medium w-10">#</th>
            <th className="px-4 py-3 font-medium">Matchup</th>
            <th className="px-4 py-3 font-medium hidden md:table-cell">Venue</th>
            <th className="px-4 py-3 font-medium text-right hidden sm:table-cell">
              Away / Home
            </th>
            <th className="px-4 py-3 font-medium text-right">
              Avg hitter (both)
            </th>
          </tr>
        </thead>
        <tbody>
          {rankings.map((m) => {
            const k = keyFor(m)
            const isOpen = open.has(k)
            return (
              <Fragment key={k}>
                <tr
                  onClick={() => toggle(k)}
                  className="border-b border-gray-50 last:border-b-0 hover:bg-gray-50/60 cursor-pointer"
                >
                  <td className="px-4 py-3 text-gray-400">{m.rank}</td>
                  <td className="px-4 py-3">
                    <p className="font-medium text-gray-900 flex items-center gap-1.5">
                      <span
                        className={`text-gray-300 text-[10px] transition-transform ${
                          isOpen ? "rotate-90" : ""
                        }`}
                      >
                        ▶
                      </span>
                      {m.matchup}
                      {m.doubleheader && (
                        <span className="shrink-0 inline-flex items-center rounded-full bg-amber-50 border border-amber-200 text-amber-700 text-[9px] font-semibold px-1.5 py-px uppercase tracking-wide">
                          Game {m.game_number}
                        </span>
                      )}
                    </p>
                    <p className="text-[11px] text-gray-400 pl-4">
                      {m.hitter_count} projected hitters
                    </p>
                  </td>
                  <td className="px-4 py-3 text-gray-400 text-xs hidden md:table-cell">
                    {m.venue ?? "—"}
                  </td>
                  <td className="px-4 py-3 text-right hidden sm:table-cell tabular-nums text-xs text-gray-500">
                    {m.away_avg != null ? m.away_avg.toFixed(1) : "—"}
                    <span className="text-gray-300"> / </span>
                    {m.home_avg != null ? m.home_avg.toFixed(1) : "—"}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end gap-2">
                      <div className="w-24 h-1.5 bg-gray-100 rounded-full overflow-hidden hidden sm:block">
                        <div
                          className="h-full bg-emerald-500 rounded-full"
                          style={{
                            width: `${(m.combined_avg / maxScore) * 100}%`,
                          }}
                        />
                      </div>
                      <span className="font-semibold text-emerald-700 tabular-nums">
                        {m.combined_avg.toFixed(1)}
                      </span>
                    </div>
                  </td>
                </tr>

                {isOpen && (
                  <tr className="bg-gray-50/60 border-b border-gray-50">
                    <td colSpan={5} className="px-4 py-3">
                      <div className="grid gap-3 sm:grid-cols-2 max-w-3xl">
                        {m.teams.map((team) => {
                          const players = team.players ?? []
                          return (
                            <div key={team.team_name}>
                              <p className="text-[11px] font-medium text-gray-500 mb-1 flex items-center gap-1.5">
                                <span className="uppercase tracking-wide">
                                  {team.side ?? ""}
                                </span>
                                <span className="text-gray-800">
                                  {team.team_name}
                                </span>
                                <span className="text-gray-300">·</span>
                                <span className="text-emerald-700 font-semibold tabular-nums">
                                  {team.avg_score.toFixed(1)} avg
                                </span>
                              </p>
                              {players.length === 0 ? (
                                <p className="text-xs text-gray-400 px-1">
                                  No lineup posted yet.
                                </p>
                              ) : (
                                <ul className="rounded-lg border border-gray-100 bg-white divide-y divide-gray-50">
                                  {players.map((p) => (
                                    <li
                                      key={p.player_id}
                                      className="flex items-center justify-between px-3 py-1.5"
                                    >
                                      <Link
                                        href={`/player/${p.player_id}`}
                                        onClick={(e) => e.stopPropagation()}
                                        className="text-sm text-gray-800 hover:text-emerald-700 hover:underline"
                                      >
                                        {p.name}
                                      </Link>
                                      <span className="text-sm font-medium text-emerald-700 tabular-nums">
                                        {p.score.toFixed(1)}
                                      </span>
                                    </li>
                                  ))}
                                </ul>
                              )}
                            </div>
                          )
                        })}
                      </div>
                    </td>
                  </tr>
                )}
              </Fragment>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
