import Link from "next/link"
import type { HotLeader, HotLeadersResponse } from "../lib/api"
import Sparkline from "./Sparkline"

const dropZero = (v: number) => v.toFixed(3).replace(/^0\./, ".")

const META: Record<
  HotLeader["stat"],
  { label: string; fmt: (v: number) => string }
> = {
  avg: { label: "AVG", fmt: dropZero },
  hr: { label: "HR", fmt: (v) => String(v) },
  ops: { label: "OPS", fmt: (v) => (v < 1 ? dropZero(v) : v.toFixed(3)) },
}

function LeaderCard({ leader }: { leader: HotLeader }) {
  const m = META[leader.stat]
  return (
    <div className="bg-white border border-gray-100 rounded-xl p-4">
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-[10px] font-semibold text-emerald-700 uppercase tracking-wider">
          Hottest {m.label}
        </span>
        <span className="text-[10px] text-gray-300 uppercase tracking-wider">
          10-day
        </span>
      </div>
      <Link
        href={`/player/${leader.player_id}`}
        className="text-sm font-medium text-gray-900 hover:underline block truncate"
      >
        {leader.name}
      </Link>
      <p className="text-xs text-gray-400 truncate">{leader.team}</p>
      <div className="flex items-end justify-between mt-1.5 gap-3">
        <p className="text-2xl font-semibold text-gray-900 leading-none">
          {m.fmt(leader.value)}
        </p>
        <div className="flex-1 min-w-0">
          <Sparkline data={leader.series} format={m.fmt} />
        </div>
      </div>
    </div>
  )
}

export default function Last10Leaders({
  data,
  loading,
}: {
  data: HotLeadersResponse | null
  loading?: boolean
}) {
  return (
    <div className="space-y-3">
      <p className="text-xs font-medium text-gray-400 uppercase tracking-wider">
        Hot hitters · last 10 days
      </p>

      {loading &&
        Array.from({ length: 3 }).map((_, i) => (
          <div
            key={i}
            className="h-32 bg-white border border-gray-100 rounded-xl animate-pulse"
          />
        ))}

      {!loading &&
        data &&
        ([data.avg_leader, data.hr_leader, data.ops_leader].filter(
          Boolean
        ) as HotLeader[]).map((l) => <LeaderCard key={l.stat} leader={l} />)}
    </div>
  )
}
