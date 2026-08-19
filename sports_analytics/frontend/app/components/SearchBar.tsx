"use client"

import { useEffect, useRef, useState } from "react"

type Props = {
  onSearch: (query: string) => void
  placeholder?: string
}

export default function SearchBar({ onSearch, placeholder }: Props) {
  const [value, setValue] = useState("")
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    return () => {
      if (timer.current) clearTimeout(timer.current)
    }
  }, [])

  function handleChange(next: string) {
    setValue(next)
    if (timer.current) clearTimeout(timer.current)
    timer.current = setTimeout(() => onSearch(next.trim()), 300)
  }

  function handleClear() {
    setValue("")
    if (timer.current) clearTimeout(timer.current)
    onSearch("")
  }

  return (
    <div className="relative w-full max-w-md">
      <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-300 text-sm">
        🔍
      </span>
      <input
        type="search"
        value={value}
        onChange={(e) => handleChange(e.target.value)}
        placeholder={placeholder ?? "Search players..."}
        aria-label="Search players"
        className="w-full border border-gray-200 rounded-full pl-9 pr-9 py-2 text-sm text-gray-900 bg-white placeholder:text-gray-300 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
      />
      {value && (
        <button
          type="button"
          onClick={handleClear}
          aria-label="Clear search"
          className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-300 hover:text-gray-500 text-sm"
        >
          ✕
        </button>
      )}
    </div>
  )
}
