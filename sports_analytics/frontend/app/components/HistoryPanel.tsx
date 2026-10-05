import { Fragment } from "react"
import type {
  HistoryResponse,
  HistorySummary,
  PropLabel,
} from "../lib/api"

const PROP_TITLE: Record<PropLabel, string> = {
  HR: "Home run",
  "1H": "1+ hits",
  "2H": "2+ hits",
  "3H": "3+ hits",
}

function money(v: number): string {
  const s = v < 0 ? "−" : "+"
  return `${s}$${Math.abs(v).toFixed(2)}`
}

function pnlClass(v: number | null): string {
  if (v === null || v === 0) return "text-gray-500"
  return v > 0 ? "text-emerald-700" : "text-red-500"
}

function pct(v: number | null): string {
  return v === null ? "—" : `${v.toFixed(1)}%`
}

// ── summary table ────────────────────────────────────────────
function SummaryTable({
  props,
  summary,
}: {
  props: PropLabel[]
  summary: Record<PropLabel, HistorySummary>
}) {
  return (
    <div className="bg-white border border-gray-100 rounded-xl overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-[11px] uppercase tracking-wider text-gray-400 border-b border-gray-100">
              <th className="text-left font-medium px-4 py-2.5">Prop</th>
              <th className="text-right font-medium px-3 py-2.5">Record</th>
              <th className="text-right font-medium px-3 py-2.5">Win %</th>
              <th className="text-right font-medium px-3 py-2.5">Avg odds</th>
              <th className="text-right font-medium px-3 py-2.5">Break-even</th>
              <th className="text-right font-medium px-3 py-2.5">P&amp;L</th>
              <th className="text-right font-medium px-4 py-2.5">ROI</th>
            </tr>
          </thead>
          <tbody>
            {props.map((p) => {
              const s = summary[p]
              return (
                <tr key={p} className="border-b border-gray-50 last:border-0">
                  <td className="px-4 py-2.5 text-gray-900 font-medium">
                    {PROP_TITLE[p]}
                  </td>
                  <td className="px-3 py-2.5 text-right tabular-nums text-gray-700">
                    {s.wins}/{s.bets}
                  </td>
                  <td className="px-3 py-2.5 text-right tabular-nums text-gray-700">
                    {pct(s.win_pct)}
                  </td>
                  <td className="px-3 py-2.5 text-right tabular-nums text-gray-500">
                    {s.avg_odds === null
                      ? "—"
                      : `${s.avg_odds > 0 ? "+" : ""}${s.avg_odds}`}
                  </td>
                  <td className="px-3 py-2.5 text-right tabular-nums text-gray-500">
                    {pct(s.breakeven_pct)}
                  </td>
                  <td
                    className={`px-3 py-2.5 text-right tabular-nums font-medium ${pnlClass(
                      s.pnl
                    )}`}
                  >
                    {money(s.pnl)}
                  </td>
                  <td
                    className={`px-4 py-2.5 text-right tabular-nums font-medium ${pnlClass(
                      s.roi
                    )}`}
                  >
                    {s.roi === null ? "—" : `${s.roi > 0 ? "+" : ""}${s.roi}%`}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ── profit-by-threshold matrix ───────────────────────────────
function ThresholdMatrix({ data }: { data: HistoryResponse }) {
  const { props, thresholds, matrix } = data
  return (
    <div className="bg-white border border-gray-100 rounded-xl overflow-hidden">
      <p className="text-xs font-medium text-gray-500 px-4 pt-3">
        Profit by model-score threshold{" "}
        <span className="text-gray-400">· profit and record for score ≥ cutoff</span>
      </p>
      <div className="overflow-x-auto mt-2">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-[11px] uppercase tracking-wider text-gray-400 border-b border-gray-50">
              <th rowSpan={2} className="text-left font-medium px-4 py-2 align-bottom">
                Score
              </th>
              {props.map((p) => (
                <th
                  key={p}
                  colSpan={3}
                  className="text-center font-medium px-3 py-1.5 border-l border-gray-100"
                >
                  {p}
                </th>
              ))}
            </tr>
            <tr className="text-[10px] uppercase tracking-wider text-gray-300 border-b border-gray-100">
              {props.map((p) => (
                <Fragment key={p}>
                  <th className="text-right font-medium px-3 py-1.5 border-l border-gray-100">
                    Profit
                  </th>
                  <th className="text-right font-medium px-3 py-1.5">% Profit</th>
                  <th className="text-right font-medium px-3 py-1.5">W/B · Win%</th>
                </Fragment>
              ))}
            </tr>
          </thead>
          <tbody>
            {thresholds.map((t, i) => (
              <tr key={t} className="border-b border-gray-50 last:border-0">
                <td className="px-4 py-2 font-medium text-gray-700 tabular-nums">
                  {t}+
                </td>
                {props.map((p) => {
                  const cell = matrix[p][i]
                  return (
                    <Fragment key={p}>
                      <td
                        className={`px-3 py-2 text-right tabular-nums border-l border-gray-100 font-medium ${pnlClass(
                          cell.profit
                        )}`}
                      >
                        {money(cell.profit)}
                      </td>
                      <td
                        className={`px-3 py-2 text-right tabular-nums text-xs font-medium ${pnlClass(
                          cell.roi
                        )}`}
                      >
                        {cell.roi === null
                          ? "—"
                          : `${cell.roi > 0 ? "+" : ""}${cell.roi}%`}
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums text-gray-400 text-xs">
                        {cell.bets === 0
                          ? "—"
                          : `${cell.wins}/${cell.bets} · ${pct(cell.win_pct)}`}
                      </td>
                    </Fragment>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ── result chip + daily log ──────────────────────────────────
function Chip({ v }: { v: number | null }) {
  if (v === null)
    return <span className="text-gray-300">—</span>
  return v === 1 ? (
    <span className="text-emerald-600 font-semibold">✓</span>
  ) : (
    <span className="text-gray-300">✗</span>
  )
}

function LogTable({ data }: { data: HistoryResponse }) {
  const { props, log } = data
  return (
    <div className="bg-white border border-gray-100 rounded-xl overflow-hidden">
      <p className="text-xs font-medium text-gray-500 px-4 pt-3">Daily log</p>
      <div className="overflow-auto max-h-[28rem] mt-2">
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-white">
            <tr className="text-[11px] uppercase tracking-wider text-gray-400 border-b border-gray-100">
              <th className="text-left font-medium px-4 py-2">Date</th>
              <th className="text-left font-medium px-3 py-2">Player</th>
              <th className="text-right font-medium px-3 py-2">Score</th>
              {props.map((p) => (
                <th key={p} className="text-center font-medium px-2 py-2">
                  {p}
                </th>
              ))}
              <th className="text-right font-medium px-4 py-2">Day P&amp;L</th>
            </tr>
          </thead>
          <tbody>
            {log.map((row, idx) => (
              <tr
                key={`${row.date}-${row.player}-${idx}`}
                className="border-b border-gray-50 last:border-0"
              >
                <td className="px-4 py-2 text-gray-500 tabular-nums whitespace-nowrap">
                  {row.date}
                </td>
                <td className="px-3 py-2 text-gray-900">{row.player}</td>
                <td className="px-3 py-2 text-right tabular-nums text-gray-700">
                  {row.score ?? "—"}
                </td>
                {props.map((p) => (
                  <td key={p} className="px-2 py-2 text-center">
                    <Chip v={row.results[p]} />
                  </td>
                ))}
                <td
                  className={`px-4 py-2 text-right tabular-nums font-medium ${pnlClass(
                    row.day_pnl
                  )}`}
                >
                  {row.day_pnl === null ? "—" : money(row.day_pnl)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export default function HistoryPanel({
  data,
  loading,
  error,
}: {
  data: HistoryResponse | null
  loading?: boolean
  error?: string | null
}) {
  if (loading) {
    return (
      <div className="space-y-4">
        {Array.from({ length: 3 }).map((_, i) => (
          <div
            key={i}
            className="h-40 bg-white border border-gray-100 rounded-xl animate-pulse"
          />
        ))}
      </div>
    )
  }
  if (error) {
    return (
      <p className="text-sm text-red-500 bg-white border border-red-100 rounded-xl p-6 text-center">
        {error}
      </p>
    )
  }
  if (!data || data.rows_logged === 0) {
    return (
      <p className="text-sm text-gray-400 bg-white border border-gray-100 rounded-xl p-6 text-center">
        No results logged yet in the tracker.
      </p>
    )
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-gray-400">
        {data.rows_logged} bets over {data.days_logged} day
        {data.days_logged === 1 ? "" : "s"}
        {data.date_range
          ? ` · ${data.date_range.start} to ${data.date_range.end}`
          : ""}{" "}
        · live from <span className="text-gray-500">{data.source}</span>
      </p>
      <SummaryTable props={data.props} summary={data.summary} />
      <ThresholdMatrix data={data} />
      <LogTable data={data} />
    </div>
  )
}
