"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { login } from "./lib/api"

export default function LoginPage() {
  const router = useRouter()
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setError(null)

    if (!username.trim() || !password.trim()) {
      setError("Please enter both a username and a password.")
      return
    }

    setSubmitting(true)
    try {
      const result = await login(username.trim(), password)
      sessionStorage.setItem("analytic_user", result.username)
      router.push("/dashboard")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed. Is the backend running?")
      setSubmitting(false)
    }
  }

  return (
    <main className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <p className="text-4xl mb-3">⚾</p>
          <h1 className="text-2xl font-semibold text-gray-900">
            Analytic Overview
          </h1>
          <p className="text-sm text-gray-400 mt-1">
            Daily MLB hitter projections &amp; matchup intelligence
          </p>
        </div>

        <form
          onSubmit={handleSubmit}
          className="bg-white border border-gray-100 rounded-2xl p-6 shadow-sm space-y-4"
        >
          <div>
            <label
              htmlFor="username"
              className="block text-xs font-medium text-gray-500 uppercase tracking-wider mb-1.5"
            >
              Username
            </label>
            <input
              id="username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Enter your username"
              autoComplete="username"
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm text-gray-900 placeholder:text-gray-300 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
            />
          </div>

          <div>
            <label
              htmlFor="password"
              className="block text-xs font-medium text-gray-500 uppercase tracking-wider mb-1.5"
            >
              Password
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter your password"
              autoComplete="current-password"
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm text-gray-900 placeholder:text-gray-300 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
            />
          </div>

          {error && (
            <p
              role="alert"
              className="text-xs text-red-600 bg-red-50 border border-red-100 rounded-lg px-3 py-2"
            >
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="w-full bg-emerald-600 hover:bg-emerald-700 disabled:opacity-60 text-white text-sm font-medium rounded-lg py-2.5 transition-colors"
          >
            {submitting ? "Signing in..." : "Sign in"}
          </button>
        </form>

        <p className="text-center text-[11px] text-gray-300 mt-4">
          Accounts aren&apos;t stored yet — any username and password will work.
        </p>
      </div>
    </main>
  )
}
