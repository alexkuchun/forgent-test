"use client"

import * as React from "react"

export type ToastKind = "success" | "error" | "info"

export interface ToastItem {
  id: number
  kind: ToastKind
  text: string
}

interface ToastContextValue {
  push: (kind: ToastKind, text: string, opts?: { duration?: number }) => void
  remove: (id: number) => void
}

const ToastContext = React.createContext<ToastContextValue | undefined>(undefined)

export function useToast(): ToastContextValue {
  const ctx = React.useContext(ToastContext)
  if (!ctx) throw new Error("useToast must be used within ToasterProvider")
  return ctx
}

export function ToasterProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = React.useState<ToastItem[]>([])

  const remove = React.useCallback((id: number) => {
    setToasts((t) => t.filter((x) => x.id !== id))
  }, [])

  const push = React.useCallback((kind: ToastKind, text: string, opts?: { duration?: number }) => {
    const id = Date.now() + Math.random()
    setToasts((t) => [...t, { id, kind, text }])
    const duration = opts?.duration ?? 3500
    window.setTimeout(() => remove(id), duration)
  }, [remove])

  return (
    <ToastContext.Provider value={{ push, remove }}>
      {children}
      <ToastViewport toasts={toasts} onClose={remove} />
    </ToastContext.Provider>
  )
}

function ToastViewport({ toasts, onClose }: { toasts: ToastItem[]; onClose: (id: number) => void }) {
  return (
    <div className="fixed bottom-4 right-4 z-50 space-y-2">
      {toasts.map((t) => (
        <div
          key={t.id}
          className={`rounded border px-3 py-2 text-sm shadow-md ${
            t.kind === "success"
              ? "border-green-700 bg-green-900/70 text-green-100"
              : t.kind === "error"
              ? "border-red-700 bg-red-900/70 text-red-100"
              : "border-blue-700 bg-blue-900/70 text-blue-100"
          }`}
        >
          <div className="flex items-start justify-between gap-4">
            <span>{t.text}</span>
            <button
              className="text-xs opacity-75 hover:opacity-100"
              onClick={() => onClose(t.id)}
              aria-label="Close"
            >
              ✕
            </button>
          </div>
        </div>
      ))}
    </div>
  )
}
