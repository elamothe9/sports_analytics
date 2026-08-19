export const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000"

export type CoreBreakdown = {
  ten_day: number
  season: number
  season_hr: number
  h2h: number
  lr_splits: number
  park_factor: number
  weather: number
  bullpen: number
}

export type TopPlayer = {
  player_id: number
  name: string
  team: string
  pitcher_id: number
  pitcher_hand: string
  venue: string
  batter_hand: string
  opp_team_id: number
  core: CoreBreakdown
  pre_h2h_score: number
  total_score?: number
  h2h_detail?: H2HDetail | null
  h2h_note?: string | null
}

export type FastScoresResponse = {
  date: string
  total_players_scored: number
  top_25: TopPlayer[]
}

export type H2HDetail = {
  avg: number | null
  ops: number | null
  pa: number
  ab?: number
  hits?: number
}

export type SplitLine = { avg: number; ops: number }

export type PlayerCardData = {
  player_id: number
  name: string
  team_id: number
  team_name: string
  bats: string
  season: { avg: number; ops: number; hr: number; pa: number }
  last_10: { avg: number; ops: number; pa?: number } | null
  splits: { vs_lhp: SplitLine; vs_rhp: SplitLine } | null
  today: {
    opponent: string
    venue: string
    side: string
    pitcher: { id: number; name: string | null; hand: string }
    total_score: number
    core_score: number
    bonus_score: number
    breakdown: { core: CoreBreakdown; bonuses: Record<string, number> }
    h2h: H2HDetail
    h2h_note: string | null
  } | null
}

export type SearchResponse = {
  query: string
  count: number
  players: PlayerCardData[]
}

export type TeamRanking = {
  rank: number
  team_id: number | null
  team_name: string
  opponent: string | null
  venue: string | null
  side: string | null
  avg_score: number
  player_count: number
}

export type TeamRankingsResponse = {
  date: string
  team_count: number
  rankings: TeamRanking[]
}

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { cache: "no-store" })
  if (!res.ok) {
    throw new Error(`Request failed (${res.status})`)
  }
  return res.json()
}

export function fetchTopPlayers(): Promise<FastScoresResponse> {
  return getJson("/api/scores/today/fast")
}

export function fetchTeamRankings(): Promise<TeamRankingsResponse> {
  return getJson("/api/teams/rankings")
}

export function searchPlayers(query: string): Promise<SearchResponse> {
  return getJson(`/api/players/search?q=${encodeURIComponent(query)}`)
}

export function fetchPlayerCard(playerId: number | string): Promise<PlayerCardData> {
  return getJson(`/api/players/${playerId}`)
}

export async function login(
  username: string,
  password: string
): Promise<{ success: boolean; username: string }> {
  const res = await fetch(`${API_URL}/api/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  })
  const data = await res.json().catch(() => null)
  if (!res.ok) {
    throw new Error(data?.detail || "Login failed")
  }
  return data
}
