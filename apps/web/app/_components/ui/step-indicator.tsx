"use client"

import * as React from "react"

export interface StepIndicatorProps {
  status: string
}

const ORDER = ["DRAFT", "UPLOADING", "PROCESSING", "READY", "FAILED"] as const

type StatusKey = typeof ORDER[number]

function statusIndex(s: string): number {
  const up = (s || "").toUpperCase()
  const idx = ORDER.indexOf(up as StatusKey)
  return idx >= 0 ? idx : 0
}

export function StepIndicator({ status }: StepIndicatorProps) {
  const idx = statusIndex(status)
  return (
    <div className="flex items-center gap-3 text-xs">
      {ORDER.map((label, i) => {
        const active = i === idx
        const done = i < idx && label !== "FAILED"
        const failed = label === "FAILED" && status.toUpperCase() === "FAILED"
        const dotCls = failed
          ? "bg-red-600"
          : active
          ? "bg-blue-500"
          : done
          ? "bg-green-600"
          : "bg-slate-700"
        const textCls = active ? "text-slate-100" : "text-slate-400"
        return (
          <div key={label} className="flex items-center gap-2">
            <div className={`h-2.5 w-2.5 rounded-full ${dotCls}`} />
            <span className={textCls}>{label}</span>
            {i < ORDER.length - 1 && <div className="h-px w-6 bg-slate-700" />}
          </div>
        )
      })}
    </div>
  )
}
