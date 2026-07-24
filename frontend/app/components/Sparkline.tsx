type SparklineProps = {
    data: number[]
    color: string
}

export default function Sparkline({ data, color }: SparklineProps) {
    const width = 160
    const height = 48
    const padding = 4

    const min = Math.min(...data)
    const max = Math.max(...data)
    const range = max - min || 1

    const points = data.map((val, i) => {
        const x = (i / (data.length - 1)) * (width - padding * 2) + padding
        const y = height - padding - ((val - min) / range) * (height - padding * 2)
        return `${x},${y}`
    })

    const pointsStr = points.join(" ")
    const lastPoint = points[points.length - 1]
    const [lastX, lastY] = lastPoint.split(",")

    const areaPoints = `${padding},${height} ${pointsStr} ${width - padding},${height}`

    return (
        <div className="mt-2 pt-2 border-t border-gray-100">
            <p className="text-[10px] text-gray-400 mb-1">Last 7 days</p>
            <svg
                viewBox={`0 0 ${width} ${height}`}
                className="w-full"
                preserveAspectRatio="none"
                height={height}
            >
                <polygon points={areaPoints} fill={color} fillOpacity={0.08} />
                <polyline
                    points={pointsStr}
                    fill="none"
                    stroke={color}
                    strokeWidth={1.5}
                    strokeLinejoin="round"
                    strokeLinecap="round"
                />
                <circle cx={lastX} cy={lastY} r={3} fill={color} />
            </svg>
            <div className="flex justify-between mt-0.5">
                <span className="text-[9px] text-gray-400">7d ago</span>
                <span className="text-[9px] text-gray-400">today</span>
            </div>
        </div>
    )
}