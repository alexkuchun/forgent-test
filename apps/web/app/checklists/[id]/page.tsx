"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Button } from "../../_components/ui/button";
import { ConfirmDialog } from "../../_components/ui/confirm-dialog";
import { Input } from "../../_components/ui/input";
import { Label } from "../../_components/ui/label";
import { StatusPill } from "../../_components/ui/status-pill";
import { StepIndicator } from "../../_components/ui/step-indicator";
import { useToast } from "../../_components/ui/toaster";

interface ChecklistDetail {
  id: string;
  title: string;
  status: string;
  meta?: Record<string, any>;
  created_at: string;
  updated_at: string;
  documents?: Array<{
    id: number;
    filename: string;
    storage_key: string;
    content_type?: string;
    size_bytes?: number;
    created_at: string;
  }>;
  items?: Array<ChecklistItem>;
  prompts?: ChecklistPrompt[];
}

interface ChecklistItem {
  id: number;
  text: string;
  category?: string;
  priority?: string;
  order_index?: number;
  completed: boolean;
}

interface ChecklistPrompt {
  id: number;
  prompt_text: string;
  prompt_type: "QUESTION" | "CONDITION";
  answer_text?: string | null;
  boolean_result?: boolean | null;
  confidence?: number | null;
  evidence?: string | null;
  page_refs?: number[];
  status: string;
  error?: string | null;
}

export default function ChecklistDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = params?.id as string;

  const [detail, setDetail] = useState<ChecklistDetail | null>(null);
  const [title, setTitle] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [message, setMessage] = useState("");
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [updatingItems, setUpdatingItems] = useState<Set<number>>(new Set());
  const { push } = useToast();

  const toggleItem = async (it: ChecklistItem) => {
    if (!detail) return;
    setUpdatingItems((s) => new Set(s).add(it.id));
    try {
      const res = await fetch(`/api/checklist-items/${it.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ completed: !it.completed }),
      });
      if (!res.ok) throw new Error(`Update failed: ${res.status}`);
      // Optimistically update local state
      setDetail((d) => {
        if (!d?.items) return d;
        return {
          ...d,
          items: d.items.map((x) =>
            x.id === it.id ? { ...x, completed: !it.completed } : x
          ),
        };
      });
      push("success", !it.completed ? "Item completed" : "Item reopened");
    } catch (e: any) {
      console.error(e);
      push("error", e.message || "Failed to update item");
    } finally {
      setUpdatingItems((s) => {
        const next = new Set(s);
        next.delete(it.id);
        return next;
      });
    }
  };

  useEffect(() => {
    const fetchDetail = async () => {
      if (!id) return;
      setLoading(true);
      try {
        const res = await fetch(`/api/checklists/${id}`);
        if (!res.ok) throw new Error(`Failed to load checklist: ${res.status}`);
        const data: ChecklistDetail = await res.json();
        setDetail(data);
        setTitle(data.title || "");
        // If items not present, try loading items list
        if (!data.items) {
          const itemsRes = await fetch(`/api/checklists/${id}/items`);
          if (itemsRes.ok) {
            const items: ChecklistItem[] = await itemsRes.json();
            setDetail((d) => (d ? { ...d, items } : d));
          }
        }
      } catch (e: any) {
        console.error(e);
        setMessage(e.message || "Failed to load checklist");
        push("error", e.message || "Failed to load checklist");
      } finally {
        setLoading(false);
      }
    };
    fetchDetail();
  }, [id]);

  const saveTitle = async () => {
    if (!id) return;
    setSaving(true);
    setMessage("");
    try {
      const res = await fetch(`/api/checklists/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title }),
      });
      if (!res.ok) throw new Error(`Rename failed: ${res.status}`);
      setMessage("Title saved");
      push("success", "Title saved");
      // Refresh detail
      const latest = await fetch(`/api/checklists/${id}`);
      if (latest.ok) setDetail(await latest.json());
    } catch (e: any) {
      console.error(e);
      setMessage(e.message || "Rename failed");
      push("error", e.message || "Rename failed");
    } finally {
      setSaving(false);
    }
  };

  const deleteChecklist = async () => {
    if (!id) return;
    setDeleting(true);
    setMessage("");
    try {
      const res = await fetch(`/api/checklists/${id}`, { method: "DELETE" });
      if (!res.ok) throw new Error(`Delete failed: ${res.status}`);
      push("success", "Checklist deleted");
      router.push("/checklists/browse");
    } catch (e: any) {
      console.error(e);
      setMessage(e.message || "Delete failed");
      push("error", e.message || "Delete failed");
    } finally {
      setDeleting(false);
      setConfirmOpen(false);
    }
  };

  return (
    <main className="container py-8 space-y-6" suppressHydrationWarning>
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Checklist</h1>
        <Link
          href="/checklists/browse"
          className="text-sm text-blue-400 hover:underline"
        >
          Back to Browse
        </Link>
      </div>

      {loading && <p className="text-sm text-slate-400">Loading…</p>}
      {!loading && !detail && (
        <p className="text-sm text-red-400">Failed to load checklist</p>
      )}

      {detail && (
        <>
          {/* Overview: status, steps, progress */}
          <section className="card space-y-3">
            <h2 className="text-lg font-medium">Overview</h2>
            <div className="flex items-center gap-3">
              <StatusPill status={detail.status} />
              <StepIndicator status={detail.status} />
            </div>
            {(() => {
              const items = detail.items || []
              const completed = items.filter((it) => it.completed).length
              const total = items.length
              const pct = total ? Math.round((completed / total) * 100) : 0
              return (
                <div className="space-y-2">
                  <div className="h-2 w-full rounded bg-slate-800 overflow-hidden">
                    <div className="h-2 bg-blue-600" style={{ width: `${pct}%` }} />
                  </div>
                  <p className="text-xs text-slate-500">{completed}/{total} completed</p>
                </div>
              )
            })()}
          </section>

          <section className="card space-y-3">
            <h2 className="text-lg font-medium">Title</h2>
            <div className="flex items-center gap-3">
              <div className="flex-1">
                <Label htmlFor="title">Title</Label>
                <Input
                  id="title"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                />
              </div>
              <Button onClick={saveTitle} disabled={saving}>
                {saving ? "Saving…" : "Save"}
              </Button>
              <Button
                onClick={() => setConfirmOpen(true)}
                disabled={deleting}
                variant="destructive"
              >
                {deleting ? "Deleting…" : "Delete"}
              </Button>
            </div>
            <p className="text-xs text-slate-500">
              ID: <span className="font-mono">{detail.id}</span> · Status:{" "}
              {detail.status} · Updated:{" "}
              {new Date(detail.updated_at).toLocaleString()}
            </p>
          </section>

          <section className="card space-y-3">
            <h2 className="text-lg font-medium">Items</h2>
            {!detail.items?.length && (
              <p className="text-sm text-slate-400">No items</p>
            )}
            {(() => {
              const items = (detail.items || []).slice()
              // group by category
              const grouped: Record<string, typeof items> = {}
              for (const it of items) {
                const cat = it.category || "General"
                if (!grouped[cat]) grouped[cat] = []
                grouped[cat].push(it)
              }
              const categories = Object.keys(grouped).sort()
              return (
                <div className="space-y-4">
                  {categories.map((cat) => {
                    const list = grouped[cat].slice().sort((a, b) => {
                      const ao = a.order_index ?? 0
                      const bo = b.order_index ?? 0
                      if (ao !== bo) return ao - bo
                      return a.id - b.id
                    })
                    const catCompleted = list.filter((i) => i.completed).length
                    return (
                      <div key={cat}>
                        <div className="mb-2 flex items-center justify-between">
                          <h3 className="text-sm font-medium text-slate-200">{cat}</h3>
                          <span className="text-xs text-slate-400">{catCompleted}/{list.length} completed</span>
                        </div>
                        <ul className="space-y-2">
                          {list.map((it) => (
                            <li key={it.id} className="flex items-start gap-3">
                              <input
                                type="checkbox"
                                className="checkbox mt-1"
                                checked={it.completed}
                                disabled={updatingItems.has(it.id)}
                                onChange={() => toggleItem(it)}
                              />
                              <div>
                                <p className={`text-slate-200 ${it.completed ? "line-through opacity-70" : ""}`}>{it.text}</p>
                                <p className="text-xs text-slate-500">{it.category || "General"} {it.priority ? `· ${it.priority}` : ""}</p>
                              </div>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )
                  })}
                </div>
              )
            })()}
          </section>

          <section className="card space-y-3">
            <h2 className="text-lg font-medium">Questions & Conditions</h2>
            {!detail.prompts?.length && (
              <p className="text-sm text-slate-400">No questions or conditions yet.</p>
            )}
            {detail.prompts?.length ? (
              <div className="space-y-4">
                {detail.prompts.map((prompt) => {
                  const answer = prompt.answer_text?.trim();
                  const status = prompt.status?.toUpperCase();
                  const isFailed = status === "FAILED";
                  const booleanResult = prompt.boolean_result;
                  const pageRefs = (prompt.page_refs || []).filter((n) => typeof n === "number");
                  return (
                    <div key={prompt.id} className="rounded border border-slate-800 bg-slate-950/60 p-4 space-y-3">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="text-xs uppercase tracking-wide text-slate-400">
                            {prompt.prompt_type === "CONDITION" ? "Condition" : "Question"}
                          </p>
                          <p className="text-sm text-slate-200 whitespace-pre-wrap">
                            {prompt.prompt_text}
                          </p>
                        </div>
                        <span
                          className={`text-xs px-2 py-1 rounded border ${
                            status === "READY"
                              ? "border-emerald-400 text-emerald-300"
                              : status === "FAILED"
                              ? "border-red-400 text-red-300"
                              : "border-slate-600 text-slate-300"
                          }`}
                        >
                          {status ?? "PENDING"}
                        </span>
                      </div>

                      {Boolean(answer) && (
                        <div className="space-y-1">
                          <p className="text-xs font-medium uppercase tracking-wide text-slate-400">
                            Answer
                          </p>
                          <p className="text-sm text-slate-200 whitespace-pre-wrap">{answer}</p>
                        </div>
                      )}

                      {prompt.prompt_type === "CONDITION" && booleanResult !== null && booleanResult !== undefined && (
                        <div className="space-y-1">
                          <p className="text-xs font-medium uppercase tracking-wide text-slate-400">
                            Evaluation
                          </p>
                          <p
                            className={`text-sm font-semibold ${
                              booleanResult ? "text-emerald-300" : "text-red-300"
                            }`}
                          >
                            {booleanResult ? "True" : "False"}
                          </p>
                        </div>
                      )}

                      {typeof prompt.confidence === "number" && (
                        <p className="text-xs text-slate-500">
                          Confidence: {Math.round(prompt.confidence * 100)}%
                        </p>
                      )}

                      {pageRefs.length > 0 && (
                        <p className="text-xs text-slate-500">
                          Pages: {pageRefs.join(", ")}
                        </p>
                      )}

                      {prompt.evidence && (
                        <div className="space-y-1">
                          <p className="text-xs font-medium uppercase tracking-wide text-slate-400">
                            Evidence
                          </p>
                          <p className="text-xs text-slate-400 whitespace-pre-wrap">
                            {prompt.evidence}
                          </p>
                        </div>
                      )}

                      {isFailed && prompt.error && (
                        <p className="text-xs text-red-400">Error: {prompt.error}</p>
                      )}
                    </div>
                  );
                })}
              </div>
            ) : null}

            {detail.meta?.promptsEvaluated && (
              <p className="text-xs text-slate-500">
                Prompts evaluated: {detail.meta.promptsEvaluated}
              </p>
            )}
          </section>
        </>
      )}

      {message && <p className="text-sm text-slate-400">{message}</p>}

      {/* Confirm Delete */}
      <ConfirmDialog
        open={confirmOpen}
        title="Delete checklist?"
        description="This action cannot be undone. The checklist and its items will be permanently deleted."
        confirmLabel="Delete"
        cancelLabel="Cancel"
        onConfirm={deleteChecklist}
        onCancel={() => setConfirmOpen(false)}
      />

      {/* Toasts are rendered globally via ToasterProvider */}
    </main>
  );
}
