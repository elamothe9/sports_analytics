"use client"

import { useCallback, useEffect, useState, useSyncExternalStore } from "react"
import { useRouter } from "next/navigation"
import {
  fetchTeamRankings,
  fetchTopPlayers,
  searchPlayers,
  type FastScoresResponse,
  type SearchResponse,
  type TeamRankingsResponse,
} from "../lib/api"
import SearchBar from "../components/SearchBar"
import TopPlayerCard from "../components/TopPlayerCard"
import PlayerSearchCard from "../components/PlayerSearchCard"
import TeamRankingsTable from "../components/TeamRankingsTable"

type Tab = "players" | "teams"

function subscribeToSession(callback: () => void) {
  window.addEventListener("storage", callback)
  return () => window.removeEventListener("storage", callback)
}

export default function DashboardPage() {
  const router = useRouter()
  const user = useSyncExternalStore(
    subscribeToSession,
    () => sessionStorage.getItem("analytic_user"),
    () => null
  )

  const [tab, setTab] = useState<Tab>("players")

  const [scores, setScores] = useState<FastScoresResponse | null>(null)
  const [scoresError, setScoresError] = useState<string | null>(null)
  const [scoresLoading, setScoresLoading] = useState(true)

  const [teams, setTeams] = useState<TeamRankingsResponse | null>(null)
  const [teamsError, setTeamsError] = useState<string | null>(null)
  const [teamsLoading, setTeamsLoading] = useState(true)

  const [query, setQuery] = useState("")
  const [search, setSearch] = useState<SearchResponse | null>(null)
  const [searchLoading, setSearchLoading] = useState(false)
  const [searchError, setSearchError] = useState<string | null>(null)

  useEffect(() => {
    if (!user) {
      router.replace("/")
    }
  }, [user, router])

  useEffect(() => {
    if (!user) return

    fetchTopPlayers()
      .then(setScores)
      .catch(() =>
        setScoresError(
          "Could not load today's projections. Make sure the backend is running."
        )
      )
      .finally(() => setScoresLoading(false))

    fetchTeamRankings()
      .then(setTeams)
      .catch(() =>
        setTeamsError(
          "Could not load team rankings. Make sure the backend is running."
        )
      )
      .finally(() => setTeamsLoading(false))
  }, [user])

  const handleSearch = useCallback((q: string) => {
    setQuery(q)
    if (q.length < 2) {
      setSearch(null)
      setSearchError(null)
      setSearchLoading(false)
      return
    }
    setSearchLoading(true)
    setSearchError(null)
    searchPlayers(q)
      .then(setSearch)
      .catch(() => {
        setSearch(null)
        setSearchError("Search failed. Make sure the backend is running.")
      })
      .finally(() => setSearchLoading(false))
  }, [])

  function handleLogout() {
    sessionStorage.removeItem("analytic_user")
    router.replace("/")
  }

  if (!user) {
    return null
  }

  const searching = query.length >= 2

  return (
    <main className="min-h-screen bg-gray-50">
      <nav className="bg-white border-b border-gray-100 px-6 py-4 flex flex-wrap items-center gap-4 justify-between">
        <span className="text-base font-medium text-gray-900">
          ⚾ Analytic Overview
        </span>
        <SearchBar onSearch={handleSearch} />
        <div className="flex items-center gap-3">
          <span className="text-xs text-gray-400 bg-gray-50 border border-gray-100 rounded-full px-3 py-1">
            {user}
          </span>
          <button
            type="button"
            onClick={handleLogout}
            className="text-xs text-gray-400 hover:text-gray-700"
          >
            Log out
          </button>
        </div>
      </nav>

      {searching ? (
        <div className="px-6 py-6 max-w-4xl mx-auto">
          <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-3">
            Search results for &ldquo;{query}&rdquo;
          </p>
          {searchLoading && (
            <p className="text-sm text-gray-400">Searching...</p>
          )}
          {searchError && <p className="text-sm text-red-500">{searchError}</p>}
          {!searchLoading && !searchError && search && (
            search.count === 0 ? (
              <p className="text-sm text-gray-400 bg-white border border-gray-100 rounded-xl p-6 text-center">
                No projected hitters match &ldquo;{query}&rdquo;.
              </p>
            ) : (
              <div className="space-y-4">
                {search.players.map((card) => (
                  <PlayerSearchCard key={card.player_id} card={card} />
                ))}
              </div>
            )
          )}
        </div>
      ) : (
        <>
          <div className="px-6 py-5 border-b border-gray-100 bg-white">
            <h1 className="text-xl font-medium text-gray-900">
              Today&apos;s board
            </h1>
            <p className="text-sm text-gray-400 mt-0.5">
              Top 25 projected hitters and team rankings
              {scores ? ` · ${scores.date}` : ""}
            </p>
            <div className="flex gap-2 mt-4">
              <button
                type="button"
                onClick={() => setTab("players")}
                className={`text-xs font-medium rounded-full px-4 py-1.5 border transition-colors ${
                  tab === "players"
                    ? "bg-gray-900 text-white border-gray-900"
                    : "bg-white text-gray-500 border-gray-200 hover:border-gray-400"
                }`}
              >
                Top 25 hitters
              </button>
              <button
                type="button"
                onClick={() => setTab("teams")}
                className={`text-xs font-medium rounded-full px-4 py-1.5 border transition-colors ${
                  tab === "teams"
                    ? "bg-gray-900 text-white border-gray-900"
                    : "bg-white text-gray-500 border-gray-200 hover:border-gray-400"
                }`}
              >
                Team rankings
              </button>
            </div>
          </div>

          <div className="px-6 py-6 max-w-4xl mx-auto">
            {tab === "players" && (
              <>
                {scoresLoading && (
                  <div className="space-y-3">
                    {Array.from({ length: 6 }).map((_, i) => (
                      <div
                        key={i}
                        className="h-24 bg-white border border-gray-100 rounded-xl animate-pulse"
                      />
                    ))}
                  </div>
                )}
                {scoresError && (
                  <p className="text-sm text-red-500 bg-white border border-red-100 rounded-xl p-6 text-center">
                    {scoresError}
                  </p>
                )}
                {!scoresLoading && !scoresError && scores && (
                  scores.top_25.length === 0 ? (
                    <p className="text-sm text-gray-400 bg-white border border-gray-100 rounded-xl p-6 text-center">
                      No projections yet — there may be no games today.
                    </p>
                  ) : (
                    <div className="space-y-3">
                      {scores.top_25.map((player, index) => (
                        <TopPlayerCard
                          key={`${player.player_id}-${player.pitcher_id}`}
                          player={player}
                          rank={index + 1}
                        />
                      ))}
                    </div>
                  )
                )}
              </>
            )}

            {tab === "teams" && (
              <>
                {teamsLoading && (
                  <div className="h-64 bg-white border border-gray-100 rounded-xl animate-pulse" />
                )}
                {teamsError && (
                  <p className="text-sm text-red-500 bg-white border border-red-100 rounded-xl p-6 text-center">
                    {teamsError}
                  </p>
                )}
                {!teamsLoading && !teamsError && teams && (
                  <>
                    <p className="text-xs text-gray-400 mb-3">
                      Teams ranked by the average model score of their
                      projected hitters — a quick signal for moneyline value.
                    </p>
                    <TeamRankingsTable rankings={teams.rankings} />
                  </>
                )}
              </>
            )}
          </div>
        </>
      )}
    </main>
  )
}
