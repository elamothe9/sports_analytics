type Props = {
  data: number[]
  format?: (v: number) => string
  height?: number
}

// Minimal single-series trend line (a sparkline). One hue; the headline value
// lives in the card, so the chart carries only the shape. Hover a point for its
// value. Non-scaling stroke keeps the line 2px regardless of container width.
export default function Sparkline({
  data,
  format = (v) => String(v),
  height = 44,
}: Props) {
  if (!data || data.length === 0) {
    return <p className="text-[11px] text-gray-300 py-3">no recent games</p>
  }

  const W = 240
  const H = height
  const pad = 6
  const min = Math.min(...data)
  const max = Math.max(...data)
  const span = max - min || 1
  const n = data.length

  const x = (i: number) =>
    n === 1 ? W / 2 : pad + (i * (W - 2 * pad)) / (n - 1)
  const y = (v: number) => H - pad - ((v - min) / span) * (H - 2 * pad)

  const pts = data.map((v, i) => [x(i), y(v)] as const)
  const line = pts
    .map(([px, py], i) => `${i ? "L" : "M"}${px.toFixed(1)},${py.toFixed(1)}`)
    .join(" ")
  const area =
    `${line} L${pts[n - 1][0].toFixed(1)},${H - pad}` +
    ` L${pts[0][0].toFixed(1)},${H - pad} Z`
  const last = pts[n - 1]

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      width="100%"
      height={H}
      preserveAspectRatio="none"
      role="img"
      aria-label="Last 10 days trend"
    >
      <path d={area} fill="rgba(16,185,129,0.12)" />
      <path
        d={line}
        fill="none"
        stroke="#059669"
        strokeWidth={2}
        strokeLinejoin="round"
        strokeLinecap="round"
        vectorEffect="non-scaling-stroke"
      />
      {pts.map(([px, py], i) => (
        <circle key={i} cx={px} cy={py} r={7} fill="transparent">
          <title>{format(data[i])}</title>
        </circle>
      ))}
      <circle cx={last[0]} cy={last[1]} r={3.5} fill="#059669" />
    </svg>
  )
}
