"use client"

import * as React from 'react'
import { useEffect, useState } from 'react'
import { Button } from '../../_components/ui/button'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { Input } from '../../_components/ui/input'
import { Label } from '../../_components/ui/label'

interface ChecklistListItem {
  id: string
  title: string
  status: string
  created_at: string
  updated_at: string
  document_count: number
}

interface ChecklistItem {
  id: number
  text: string
  category?: string
  priority?: string
  order_index?: number
  completed: boolean
}

export default function BrowseChecklistsPage() {
  const [list, setList] = useState<ChecklistListItem[]>([])
  const [loading, setLoading] = useState(false)
  const [query, setQuery] = useState('')
  const pathname = usePathname()

  useEffect(() => {
    const fetchList = async () => {
      setLoading(true)
      try {
        const res = await fetch(`/api/checklists`)
        if (!res.ok) throw new Error(`List failed: ${res.status}`)
        const data: ChecklistListItem[] = await res.json()
        setList(data)
      } catch (e) {
        console.error(e)
      } finally {
        setLoading(false)
      }
    }
    fetchList()
  }, [])

  // No inline items view anymore; dedicated detail page covers items.

  return (
    <main className="container py-8 space-y-6" suppressHydrationWarning>
      <nav className="border-b border-slate-800 mb-2">
        <div className="flex gap-4">
          <Link
            href="/checklists"
            className={`px-3 py-2 text-sm ${pathname === '/checklists' ? 'text-slate-100 border-b-2 border-blue-500' : 'text-slate-400 hover:text-slate-200'}`}
          >
            Add Checklist
          </Link>
          <Link
            href="/checklists/browse"
            className={`px-3 py-2 text-sm ${pathname?.startsWith('/checklists/browse') ? 'text-slate-100 border-b-2 border-blue-500' : 'text-slate-400 hover:text-slate-200'}`}
          >
            Browse Checklists
          </Link>
        </div>
      </nav>
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">All Checklists</h1>
        <a href="/checklists" className="text-sm text-blue-400 hover:underline">Go to Create/Process</a>
      </div>

      <div className="max-w-md">
        <Label htmlFor="search" className="sr-only">Search</Label>
        <Input
          id="search"
          placeholder="Search by title, id, or status"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>

      {loading && <p className="text-sm text-slate-400">Loading…</p>}
      {!loading && list.length === 0 && (
        <p className="text-sm text-slate-400">No checklists yet. Create one on the Create/Process page.</p>
      )}

      <ul className="space-y-3">
        {list
          .filter((c) => {
            const q = query.trim().toLowerCase()
            if (!q) return true
            return (
              c.title?.toLowerCase().includes(q) ||
              c.id.toLowerCase().includes(q) ||
              c.status.toLowerCase().includes(q)
            )
          })
          .map((c) => (
          <li key={c.id} className="card">
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="flex items-center gap-3">
                  <p className="font-medium text-slate-100">{c.title}</p>
                  <span className="rounded bg-slate-800 px-2 py-0.5 text-xs text-slate-300">{c.status}</span>
                </div>
                <p className="mt-1 text-xs text-slate-500">
                  ID: <span className="font-mono">{c.id}</span> · Docs: {c.document_count} · Updated: {new Date(c.updated_at).toLocaleString()}
                </p>
              </div>
              <div className="flex gap-2">
                <a href={`/checklists/${encodeURIComponent(c.id)}`} className="text-sm text-blue-400 hover:underline">Open</a>
              </div>
            </div>
          </li>
        ))}
      </ul>
    </main>
  )
}
