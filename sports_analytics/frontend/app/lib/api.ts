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

export type ActiveBonus = {
  key: string
  label: string
  points: number
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
  opp_team?: string | null
  pitcher_name?: string | null
  game_number?: number
  doubleheader?: boolean
  game_date?: string | null
  game_status?: string | null
  abstract_state?: string | null
  core: CoreBreakdown
  pre_h2h_score: number
  total_score?: number
  bonus_score?: number
  active_bonuses?: ActiveBonus[]
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

export type SplitLine = { avg: number; ops: number; hr: number; ab: number }

export type PlayerCardData = {
  player_id: number
  name: string
  team_id: number
  team_name: string
  bats: string
  season: { avg: number; ops: number; hr: number; ab: number; pa: number }
  last_10: { avg: number; ops: number; pa?: number; hr: number; ab: number } | null
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
    active_bonuses?: ActiveBonus[]
    h2h: H2HDetail
    h2h_note: string | null
  } | null
}

export type SearchResponse = {
  query: string
  count: number
  players: PlayerCardData[]
}

export type TeamRankingPlayer = {
  player_id: number
  name: string
  score: number
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
  players?: TeamRankingPlayer[]
}

export type TeamRankingsResponse = {
  date: string
  team_count: number
  rankings: TeamRanking[]
}

export type MatchupTeam = {
  team_name: string
  side: "home" | "away" | null
  avg_score: number
  player_count: number
  players?: TeamRankingPlayer[]
}

export type MatchupRanking = {
  rank: number
  matchup: string
  home_team: string | null
  away_team: string | null
  venue: string | null
  game_number: number
  doubleheader: boolean
  combined_avg: number
  home_avg: number | null
  away_avg: number | null
  hitter_count: number
  teams: MatchupTeam[]
}

export type MatchupRankingsResponse = {
  date: string
  matchup_count: number
  rankings: MatchupRanking[]
}

export type HotLeader = {
  player_id: number
  name: string
  team: string
  stat: "avg" | "hr" | "ops"
  value: number
  pa: number | null
  series: number[]
}

export type HotLeadersResponse = {
  days: number
  avg_leader: HotLeader | null
  hr_leader: HotLeader | null
  ops_leader: HotLeader | null
}

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { cache: "no-store" })
  if (!res.ok) {
    throw new Error(`Request failed (${res.status})`)
  }
  return res.json()
}

// Lightweight in-memory cache for the heavy dashboard endpoints. Returning to
// the dashboard within the TTL reuses the last result instantly instead of
// re-hitting the backend (which re-scores the whole slate on every call).
type CacheEntry = { at: number; promise: Promise<unknown> }
const _cache = new Map<string, CacheEntry>()
const DASHBOARD_TTL_MS = 90_000

function cachedGet<T>(path: string): Promise<T> {
  const hit = _cache.get(path)
  if (hit && Date.now() - hit.at < DASHBOARD_TTL_MS) {
    return hit.promise as Promise<T>
  }
  const promise = getJson<T>(path).catch((err) => {
    _cache.delete(path) // don't cache failures
    throw err
  })
  _cache.set(path, { at: Date.now(), promise })
  return promise as Promise<T>
}

/** Clear the dashboard cache (e.g. to force a fresh pull). */
export function invalidateDashboardCache(): void {
  _cache.clear()
}

export function fetchTopPlayers(): Promise<FastScoresResponse> {
  return cachedGet("/api/scores/today/fast")
}

export function fetchTeamRankings(): Promise<TeamRankingsResponse> {
  return cachedGet("/api/teams/rankings")
}

export function fetchMatchupRankings(): Promise<MatchupRankingsResponse> {
  return cachedGet("/api/matchups/rankings")
}

export type ScoreboardGame = {
  game_id: number
  game_number: number
  game_date: string | null
  status: string | null
  abstract_state: string | null // Preview | Live | Final
  inning: number | null
  inning_state: string | null
  away_name: string
  home_name: string
  away_abbr: string | null
  home_abbr: string | null
  away_runs: number | null
  home_runs: number | null
}

export type ScoreboardResponse = {
  as_of: string
  games: ScoreboardGame[]
}

// Live scores change minute to minute, so this bypasses the dashboard cache.
export function fetchScoreboard(): Promise<ScoreboardResponse> {
  return getJson("/api/scoreboard")
}

export function fetchHotLeaders(): Promise<HotLeadersResponse> {
  return cachedGet("/api/leaders/hot")
}

export type PropLabel = "HR" | "1H" | "2H" | "3H"

export type HistorySummary = {
  bets: number
  wins: number
  win_pct: number | null
  avg_odds: number | null
  breakeven_pct: number | null
  pnl: number
  roi: number | null
}

export type HistoryMatrixCell = {
  cutoff: number
  bets: number
  wins: number
  win_pct: number | null
  roi: number | null
  profit: number
}

export type HistoryRow = {
  date: string
  player: string
  team: string
  score: number | null
  results: Record<PropLabel, number | null>
  odds: Record<PropLabel, number | null>
  pnl: Record<PropLabel, number | null>
  day_pnl: number | null
}

export type HistoryResponse = {
  source: string
  rows_logged: number
  days_logged: number
  date_range: { start: string; end: string } | null
  props: PropLabel[]
  thresholds: number[]
  summary: Record<PropLabel, HistorySummary>
  matrix: Record<PropLabel, HistoryMatrixCell[]>
  log: HistoryRow[]
}

// Reads the local spreadsheet — cheap, and should reflect edits immediately,
// so it is intentionally NOT run through the dashboard cache.
export function fetchHistory(): Promise<HistoryResponse> {
  return getJson("/api/history")
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
