"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { fetchPlayerCard, type PlayerCardData } from "../../lib/api"
import PlayerSearchCard from "../../components/PlayerSearchCard"

export default function PlayerProfile({ playerId }: { playerId: string }) {
  const [card, setCard] = useState<PlayerCardData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchPlayerCard(playerId)
      .then(setCard)
      .catch(() =>
        setError(
          "Could not load this player. They may not be a projected hitter, or the backend may be offline."
        )
      )
      .finally(() => setLoading(false))
  }, [playerId])

  return (
    <main className="min-h-screen bg-gray-50">
      <nav className="bg-white border-b border-gray-100 px-6 py-4 flex items-center justify-between">
        <span className="text-base font-medium text-gray-900">
          ⚾ Analytic Overview
        </span>
        <Link
          href="/dashboard"
          className="text-xs text-gray-400 hover:text-gray-700"
        >
          ← Back to dashboard
        </Link>
      </nav>

      <div className="px-6 py-6 max-w-3xl mx-auto">
        {loading && (
          <div className="h-64 bg-white border border-gray-100 rounded-xl animate-pulse" />
        )}
        {error && (
          <p className="text-sm text-red-500 bg-white border border-red-100 rounded-xl p-6 text-center">
            {error}
          </p>
        )}
        {card && <PlayerSearchCard card={card} />}
      </div>
    </main>
  )
}
