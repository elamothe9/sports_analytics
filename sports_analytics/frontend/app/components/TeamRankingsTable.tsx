"use client"

import { Fragment, useState } from "react"
import Link from "next/link"
import type { TeamRanking } from "../lib/api"

export default function TeamRankingsTable({
  rankings,
}: {
  rankings: TeamRanking[]
}) {
  const [open, setOpen] = useState<Set<string>>(new Set())

  if (rankings.length === 0) {
    return (
      <p className="text-sm text-gray-400 bg-white border border-gray-100 rounded-xl p-6 text-center">
        No team rankings available — check back once today&apos;s slate is posted.
      </p>
    )
  }

  const maxScore = Math.max(...rankings.map((t) => t.avg_score), 1)

  function toggle(name: string) {
    setOpen((prev) => {
      const next = new Set(prev)
      if (next.has(name)) next.delete(name)
      else next.add(name)
      return next
    })
  }

  return (
    <div className="bg-white border border-gray-100 rounded-xl overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-[10px] text-gray-400 uppercase tracking-wider border-b border-gray-100">
            <th className="px-4 py-3 font-medium w-10">#</th>
            <th className="px-4 py-3 font-medium">Team</th>
            <th className="px-4 py-3 font-medium hidden sm:table-cell">
              Opponent
            </th>
            <th className="px-4 py-3 font-medium hidden md:table-cell">Venue</th>
            <th className="px-4 py-3 font-medium text-right">Avg hitter score</th>
          </tr>
        </thead>
        <tbody>
          {rankings.map((team) => {
            const isOpen = open.has(team.team_name)
            const players = team.players ?? []
            return (
              <Fragment key={`${team.team_name}-${team.rank}`}>
                <tr
                  onClick={() => toggle(team.team_name)}
                  className="border-b border-gray-50 last:border-b-0 hover:bg-gray-50/60 cursor-pointer"
                >
                  <td className="px-4 py-3 text-gray-400">{team.rank}</td>
                  <td className="px-4 py-3">
                    <p className="font-medium text-gray-900 flex items-center gap-1.5">
                      <span
                        className={`text-gray-300 text-[10px] transition-transform ${
                          isOpen ? "rotate-90" : ""
                        }`}
                      >
                        ▶
                      </span>
                      {team.team_name}
                    </p>
                    <p className="text-[11px] text-gray-400 pl-4">
                      {team.player_count} projected hitters
                      {team.side ? ` · ${team.side}` : ""}
                    </p>
                  </td>
                  <td className="px-4 py-3 text-gray-500 hidden sm:table-cell">
                    {team.opponent ?? "—"}
                  </td>
                  <td className="px-4 py-3 text-gray-400 text-xs hidden md:table-cell">
                    {team.venue ?? "—"}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end gap-2">
                      <div className="w-24 h-1.5 bg-gray-100 rounded-full overflow-hidden hidden sm:block">
                        <div
                          className="h-full bg-emerald-500 rounded-full"
                          style={{
                            width: `${(team.avg_score / maxScore) * 100}%`,
                          }}
                        />
                      </div>
                      <span className="font-semibold text-emerald-700 tabular-nums">
                        {team.avg_score.toFixed(1)}
                      </span>
                    </div>
                  </td>
                </tr>

                {isOpen && (
                  <tr className="bg-gray-50/60 border-b border-gray-50">
                    <td colSpan={5} className="px-4 py-3">
                      {players.length === 0 ? (
                        <p className="text-xs text-gray-400 px-1">
                          No player detail available for this team.
                        </p>
                      ) : (
                        <ul className="rounded-lg border border-gray-100 bg-white divide-y divide-gray-50 max-w-md">
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
