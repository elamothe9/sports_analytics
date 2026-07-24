import Link from "next/link"
import Sparkline from "./Sparkline"

type Player = {
    name: string
    team: string
    player_id: number
    stats: {
        hr: number
        avg: number
        ops: number
    }
    featured_stat: "hr" | "avg" | "ops"
    sparkline: number[]
}

const config = {
    hr: {
        label: "Home runs",
        color: "#D85A30",
        badgeClass: "bg-orange-50 text-orange-800",
        valueClass: "text-orange-700",
        icon: "🔥",
    },
    avg: {
        label: "Batting avg",
        color: "#1D9E75",
        badgeClass: "bg-emerald-50 text-emerald-800",
        valueClass: "text-emerald-700",
        icon: "📈",
    },
    ops: {
        label: "OPS",
        color: "#378ADD",
        badgeClass: "bg-blue-50 text-blue-800",
        valueClass: "text-blue-700",
        icon: "📊",
    },
}

export default function PlayerCard({ player }: { player: Player }) {
    const { featured_stat, stats, name, team, player_id, sparkline } = player
    const { label, color, badgeClass, valueClass, icon } = config[featured_stat]

    const initials = name
        .split(" ")
        .map((n) => n[0])
        .join("")
        .slice(0, 2)
        .toUpperCase()

    return (
        <Link href={`/player/${player_id}`} className="block">
            <div className="bg-white border border-gray-100 rounded-xl p-4 hover:border-gray-300 transition-colors cursor-pointer h-full">

        <span className={`inline-flex items-center gap-1 text-xs font-medium px-2 py-1 rounded-md mb-3 ${badgeClass}`}>
          {icon} {label}
        </span>

                <div className={`w-9 h-9 rounded-full flex items-center justify-center text-xs font-medium mb-2 ${badgeClass}`}>
                    {initials}
                </div>

                <p className="text-sm font-medium text-gray-900">{name}</p>
                <p className="text-xs text-gray-400 mb-3">{team}</p>

                <div className="space-y-0.5">
                    {(["hr", "avg", "ops"] as const).map((stat) => (
                        <div key={stat} className="flex justify-between items-center py-1 border-t border-gray-50">
                            <span className="text-xs text-gray-400 uppercase">{stat}</span>
                            <span className={`text-xs font-medium ${stat === featured_stat ? valueClass : "text-gray-700"}`}>
                {stat === "hr" ? stats.hr : stats[stat].toFixed(3)}
              </span>
                        </div>
                    ))}
                </div>

                <Sparkline data={sparkline} color={color} />

                <p className="text-[10px] text-gray-300 flex items-center gap-1 mt-2">
                    → View profile
                </p>
            </div>
        </Link>
    )
}