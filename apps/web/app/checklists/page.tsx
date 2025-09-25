"use client"

import * as React from 'react'
import { useState, useEffect } from 'react'
import { Button } from '../_components/ui/button'
import { Input } from '../_components/ui/input'
import { Label } from '../_components/ui/label'
import Link from 'next/link'
import { usePathname, useSearchParams } from 'next/navigation'


interface ChecklistDetail {
  id: string
  title: string
  status: string
  meta?: Record<string, any>
  created_at: string
  updated_at: string
  documents: Array<{
    id: number
    filename: string
    storage_key: string
    content_type?: string
    size_bytes?: number
    created_at: string
  }>
  items?: Array<ChecklistItem>
}

interface ChecklistItem {
  id: number
  text: string
  category?: string
  priority?: string
  order_index?: number
  completed: boolean
}

async function fileToBase64(file: File): Promise<string> {
  const buff = await file.arrayBuffer()
  const bytes = new Uint8Array(buff)
  let binary = ''
  for (let i = 0; i < bytes.byteLength; i++) binary += String.fromCharCode(bytes[i])
  return btoa(binary)
}

export default function ChecklistsPage() {
  const [title, setTitle] = useState('')
  const [checklistId, setChecklistId] = useState<string>('')
  const [detail, setDetail] = useState<ChecklistDetail | null>(null)
  const [file, setFile] = useState<File | null>(null)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const pathname = usePathname()
  const searchParams = useSearchParams()

  

  // If cid is present in query, preselect and load that checklist
  useEffect(() => {
    const cid = searchParams.get('cid')
    if (cid) {
      setChecklistId(cid)
      refreshDetail(cid)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams])

  const createChecklist = async () => {
    setBusy(true)
    setMessage('Creating checklist...')
    try {
      const res = await fetch(`/api/checklists`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: title || undefined }),
      })
      if (!res.ok) throw new Error(`Create failed: ${res.status}`)
      const data = await res.json()
      setChecklistId(data.id)
      await refreshDetail(data.id)
      setMessage('Checklist created')
    } catch (e: any) {
      console.error(e)
      setMessage(e.message || 'Create failed')
    } finally {
      setBusy(false)
    }
  }

  const refreshDetail = async (id = checklistId): Promise<ChecklistDetail | null> => {
    if (!id) return null
    const res = await fetch(`/api/checklists/${id}`)
    if (res.ok) {
      const data: ChecklistDetail = await res.json()
      setDetail(data)
      return data
    }
    return null
  }

  const uploadPdf = async () => {
    if (!checklistId) return alert('Create or select a checklist first')
    if (!file) return alert('Choose a PDF file')
    setBusy(true)
    setMessage('Uploading PDF...')
    try {
      const b64 = await fileToBase64(file)
      const res = await fetch(`/api/checklists/${checklistId}/upload`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filename: file.name, base64: b64, content_type: 'application/pdf' }),
      })
      if (!res.ok) throw new Error(`Upload failed: ${res.status}`)
      await refreshDetail()
      setMessage('Upload complete')
    } catch (e: any) {
      console.error(e)
      setMessage(e.message || 'Upload failed')
    } finally {
      setBusy(false)
    }
  }

  const startProcessing = async () => {
    if (!checklistId) return alert('Create or select a checklist first')
    setBusy(true)
    setMessage('Starting processing...')
    try {
      const res = await fetch(`/api/checklists/${checklistId}/process`, { method: 'POST' })
      if (!res.ok) throw new Error(`Process failed: ${res.status}`)
      setMessage('Processing started; polling status...')
      // poll until READY or FAILED
      const start = Date.now()
      const poll = async () => {
        const latest = await refreshDetail()
        const status = latest?.status
        if (status === 'READY' || status === 'FAILED') {
          setBusy(false)
          setMessage(`Processing ${status}`)
          return
        }
        if (Date.now() - start > 5 * 60 * 1000) {
          setBusy(false)
          setMessage('Processing timed out')
          return
        }
        setTimeout(poll, 3000)
      }
      setTimeout(poll, 2000)
    } catch (e: any) {
      console.error(e)
      setBusy(false)
      setMessage(e.message || 'Process failed')
    }
  }

  const toggleCompleted = async (item: ChecklistItem) => {
    if (!checklistId) return
    const res = await fetch(`/api/checklist-items/${item.id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ completed: !item.completed }),
    })
    if (res.ok) refreshDetail()
  }

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
      <h1 className="text-2xl font-semibold">Forgent Checklist</h1>

      <section className="card space-y-3">
        <h2 className="text-lg font-medium">1) Create Checklist</h2>
        <div className="flex items-center gap-3">
          <div className="flex-1">
            <Label htmlFor="title">Title</Label>
            <Input id="title" placeholder="Untitled Checklist" value={title} onChange={(e) => setTitle(e.target.value)} />
          </div>
          <Button onClick={createChecklist} disabled={busy}>Create</Button>
        </div>
        {checklistId && (
          <p className="text-sm text-slate-400">Checklist ID: <span className="font-mono">{checklistId}</span></p>
        )}
      </section>

      <section className="card space-y-3">
        <h2 className="text-lg font-medium">2) Upload PDF</h2>
        <input
          type="file"
          accept="application/pdf"
          onChange={(e) => setFile(e.target.files?.[0] || null)}
          className="block text-sm text-slate-200"
        />
        <div className="flex items-center gap-3">
          <Button onClick={uploadPdf} disabled={busy || !file || !checklistId}>Upload</Button>
          <Button onClick={() => refreshDetail()} variant="ghost">Refresh</Button>
        </div>
        {detail?.documents?.length ? (
          <ul className="list-disc pl-6 text-sm text-slate-300">
            {detail.documents.map((d) => (
              <li key={d.id}>{d.filename} ({d.size_bytes ? `${d.size_bytes} bytes` : 'size unknown'})</li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-slate-400">No documents yet</p>
        )}
      </section>

      <section className="card space-y-3">
        <h2 className="text-lg font-medium">3) Process</h2>
        <div className="flex items-center gap-3">
          <Button onClick={startProcessing} disabled={busy || !checklistId}>Start</Button>
          <Button onClick={() => refreshDetail()} variant="ghost">Poll once</Button>
        </div>
        <div className="text-sm text-slate-300">
          <p>Status: <span className="font-mono">{detail?.status ?? 'N/A'}</span></p>
          {detail?.meta?.processingSeconds && (
            <p>processingSeconds: {detail.meta.processingSeconds}</p>
          )}
        </div>
      </section>

      <section className="card space-y-3">
        <h2 className="text-lg font-medium">4) Items</h2>
        {!detail?.items?.length && <p className="text-sm text-slate-400">No items yet</p>}
        <ul className="space-y-2">
          {detail?.items?.map((it) => (
            <li key={it.id} className="flex items-start gap-3">
              <input
                className="checkbox mt-1"
                type="checkbox"
                checked={it.completed}
                onChange={() => toggleCompleted(it)}
              />
              <div>
                <p className={`text-slate-200 ${it.completed ? 'line-through opacity-70' : ''}`}>{it.text}</p>
                <p className="text-xs text-slate-500">{it.category || 'General'} {it.priority ? `· ${it.priority}` : ''}</p>
              </div>
            </li>
          ))}
        </ul>
      </section>

      {message && <p className="text-sm text-slate-400">{message}</p>}
    </main>
  )
}
