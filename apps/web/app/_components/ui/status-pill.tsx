"use client"

import * as React from "react"

export interface StatusPillProps {
  status: string
}

export function StatusPill({ status }: StatusPillProps) {
  const s = (status || "").toUpperCase()
  let cls = "bg-slate-800 text-slate-200"
  switch (s) {
    case "DRAFT":
      cls = "bg-slate-800 text-slate-200"
      break
    case "UPLOADING":
      cls = "bg-amber-700 text-amber-100"
      break
    case "PROCESSING":
      cls = "bg-blue-700 text-blue-100"
      break
    case "READY":
      cls = "bg-green-700 text-green-100"
      break
    case "FAILED":
      cls = "bg-red-700 text-red-100"
      break
  }
  return (
    <span className={`inline-flex items-center rounded px-2 py-0.5 text-xs ${cls}`}>
      {s || "UNKNOWN"}
    </span>
  )
}
