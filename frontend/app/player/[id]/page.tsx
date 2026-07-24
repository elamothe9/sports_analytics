export default function PlayerPage({ params }: { params: { id: string } }) {
    return (
        <div className="p-8">
            <h1 className="text-xl font-medium text-gray-800">
                Player profile coming soon
            </h1>
            <p className="text-gray-400 text-sm mt-1">Player ID: {params.id}</p>
        </div>
    )
}