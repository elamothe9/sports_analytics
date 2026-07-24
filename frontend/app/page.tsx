import PlayerCard from "./components/PlayerCard"

type Player = {
  name: string
  team: string
  player_id: number
  stats: { hr: number; avg: number; ops: number }
  featured_stat: "hr" | "avg" | "ops"
  sparkline: number[]
}

type LeadersResponse = {
  hr_leader: Player
  avg_leader: Player
  ops_leader: Player
}

async function getLeaders(): Promise<LeadersResponse | null> {
  try {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000"
    const res = await fetch(`${apiUrl}/api/leaders`, {
      cache: "no-store",
    })
    if (!res.ok) return null
    return res.json()
  } catch (err) {
    console.error("Failed to fetch leaders:", err)
    return null
  }
}

export default async function Home() {
  const data = await getLeaders()

  const players = [
    { ...data.hr_leader, sparkline: [0, 1, 1, 2, 3, 4, 6] },
    { ...data.avg_leader, sparkline: [0.28, 0.29, 0.30, 0.31, 0.32, 0.33, 0.336] },
    { ...data.ops_leader, sparkline: [0.85, 0.88, 0.91, 0.95, 0.99, 1.02, 1.075] },
  ]

  return (
      <main className="min-h-screen bg-gray-50">
        <nav className="bg-white border-b border-gray-100 px-6 py-4 flex items-center justify-between">
        <span className="text-base font-medium text-gray-900">
          ⚾ Analytic Overview
        </span>
          <div className="flex items-center gap-3">
          <span className="text-xs text-gray-400 bg-gray-50 border border-gray-100 rounded-full px-3 py-1">
            Last 7 days
          </span>
            <button className="flex flex-col gap-1 p-1" aria-label="menu">
              <div className="w-5 h-px bg-gray-700" />
              <div className="w-5 h-px bg-gray-700" />
              <div className="w-5 h-px bg-gray-700" />
            </button>
          </div>
        </nav>

        <div className="px-6 py-5 border-b border-gray-100 bg-white">
          <h1 className="text-xl font-medium text-gray-900">Top performers</h1>
          <p className="text-sm text-gray-400 mt-0.5">
            Hottest hitters over the last 7 days · click a card to view player profile
          </p>
        </div>

        <div className="px-6 py-5">
          <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-3">
            Hot hitters this week
          </p>
          <div className="grid grid-cols-3 gap-4">
            {players.map((player) => (
                <PlayerCard key={player.player_id} player={player} />
            ))}
          </div>
        </div>
      </main>
  )
}