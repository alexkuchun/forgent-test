# Forgent Checklist: LLM Operator Guide (Railway + FastAPI + Next.js)

This playbook is written for an LLM assistant to reproduce what we are building: deploy a monorepo with a FastAPI backend, a Dramatiq worker, and a Next.js frontend to Railway; configure Postgres, AWS S3, and Gemini; and implement/test the checklist workflow (create/list/get, upload PDF to S3, queue a processing job, and poll results). It also documents pitfalls we already encountered so you can avoid them.


---

## 1) Scope and Architecture

- **Goal**: Users upload PDFs, the backend stores them in S3, a Gemini-powered worker processes text into structured requirements, and the results are persisted in Postgres for the web UI.
- **Monorepo**:
  - `services/api/` — FastAPI app (Python)
  - `services/worker/` — Dramatiq worker (Python)
  - `apps/web/` — Next.js app (Node)
- **Infra**: Railway for hosting (services: API, Web, Worker, Postgres, Redis). AWS S3 (or compatible) for files. Google Gemini for extraction/repair plus optional Google Vision OCR.

---

## 2) Prerequisites

{{ ... }}
- Railway account and a Railway project
- AWS account with an S3 bucket + IAM user and keys (or S3-compatible storage)
- Google Gemini API key (Google AI Studio)
- Optional: Google Cloud Vision service account JSON (base64-encoded) for OCR fallback
- Local dev: macOS/Linux with curl, jq (optional), base64 tools

---

## 3) Railway Services Setup (High Level)

- Create a Railway project (or use existing).
- Add a Postgres service. Copy its `DATABASE_URL`.
- Add an API service from the `services/api/` subdirectory.
  - Root directory: `services/api`
  - Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Add a Worker service from the `services/worker/` subdirectory.
  - Root directory: `services/worker`
  - Start command: `python -m dramatiq worker.main --processes 2 --threads 8`
- Add a Web service from `apps/web/` subdirectory.
  - Root directory: `apps/web`
  - Start command: `next start -p $PORT`
- Add a Redis database (used by Dramatiq) and note its internal URL (`redis://...railway.internal:6379`).
- Configure service environment variables (see sections below).

---

## 4) API Service Environment Variables

- Required for DB:
  - `DATABASE_URL` — use Railway Postgres URL
    - IMPORTANT: Prefer `postgresql+psycopg://USER:PASS@HOST:PORT/DB`.
    - If Railway gives `postgresql://...` or `postgres://...`, the code auto-upgrades it to the psycopg v3 driver, so both should work.
- Required for S3:
  - `AWS_REGION`
  - `AWS_ACCESS_KEY_ID`
  - `AWS_SECRET_ACCESS_KEY`
  - `S3_BUCKET`
- Required for Anthropic:
  - `ANTHROPIC_API_KEY`
  - Optional: `ANTHROPIC_MODEL` (default `claude-3-5-sonnet-20241022`)
- Processing mode:
  - `LOCAL_SYNC_PROCESSOR=1` (run background tasks in-process; no Redis needed)
- CORS:
  - `ALLOWED_ORIGINS=https://<YOUR-WEB>.up.railway.app` (comma-separated list, localhost already allowed)
- Storage mocking (usually keep off when integrating for real):
  - `MOCK_STORAGE=0` or unset

---

## 5) AWS S3 and IAM Policy

Create a dedicated IAM user with these minimal permissions for your bucket:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:ListBucket"],
      "Resource": "arn:aws:s3:::YOUR_BUCKET"
    },
    {
      "Effect": "Allow",
      "Action": ["s3:PutObject", "s3:GetObject", "s3:DeleteObject"],
      "Resource": "arn:aws:s3:::YOUR_BUCKET/*"
    }
  ]
}
```

> Note: S3 permissions are split between the bucket itself and objects within the bucket. `s3:ListBucket` targets the bucket ARN (no trailing `/*`). Object-level actions like `s3:PutObject`, `s3:GetObject`, and `s3:DeleteObject` must target `arn:aws:s3:::YOUR_BUCKET/*`.

Common mistakes:

- Using only the bucket ARN (`arn:aws:s3:::YOUR_BUCKET`) for object actions (will cause `AccessDenied` on PutObject/GetObject).
- Wrong region in the client versus the bucket’s region.
- Bucket policy that denies writes; if present, review conditions.

Set `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and `S3_BUCKET` in the API service on Railway.

---

## 6) FastAPI Backend: What’s Implemented

Files of interest:

- `services/api/app/main.py`: FastAPI app, CORS, routes, startup table creation, processing kickoff
- `services/api/app/models.py`: SQLAlchemy models (Checklist, Document, ChecklistItem, statuses)
- `services/api/app/schemas.py`: Pydantic models
- `services/api/app/db.py`: engine/session; auto-normalizes `DATABASE_URL` to psycopg v3
- `services/api/app/storage.py`: S3 upload/download helpers
- `services/api/app/jobs.py`: processing pipeline using S3 + Anthropic

Endpoints:

- `GET /health` — sanity check
- `POST /api/checklists` and `POST /api/checklists/` — create a checklist
  - Body: `{ "title": "Optional title" }` — title is optional; defaults to "Untitled Checklist"
- `GET /api/checklists` — list checklists with document counts
- `GET /api/checklists/{id}` — checklist detail with documents
- `POST /api/checklists/{id}/upload` — upload base64 PDF to S3, create `Document`
- `POST /api/checklists/{id}/process` — run processing in BackgroundTask

---

## 7) Critical Pitfalls We Already Solved (Avoid These)

- **psycopg2 import error on Railway**

  - Symptom: `ModuleNotFoundError: No module named 'psycopg2'` during app start.
  - Root cause: SQLAlchemy defaulted to psycopg2 when using `postgresql://...` URLs.
  - Fix: We either set `DATABASE_URL` to `postgresql+psycopg://...` or rely on code in `app/db.py` that auto-converts `postgres://`/`postgresql://`/`+psycopg2://` to `postgresql+psycopg://`.

- **POST turning into GET / trailing slash issues**

  - Symptom: Logs show `GET /api/checklists` instead of `POST`. Trailing slash sends `307` then shows `GET`.
  - Causes:
    - Client actually sent GET (browser bar, link, form default method).
    - A hop using `301/302` converts POST → GET (e.g., http→https). Always use https and correct host.
    - Missing `Content-Type: application/json` or missing JSON body in some tools.
  - Fixes:
    - We added a second route `POST /api/checklists/` to avoid redirect for POST.
    - Always call the API host, not the web host.
    - Use curl or Swagger UI to verify the method reaching the API.

- **CORS**

  - If calling from the web app, add your web origin to `ALLOWED_ORIGINS`. Localhost is allowed by default.

- **S3 403**
  - Usually wrong bucket/region or incomplete IAM permissions.

---

## 8) Verify the API is Healthy

- Health:

```bash
curl -s https://<API_HOST>/health
```

- OpenAPI has the POST route:

```bash
curl -s https://<API_HOST>/openapi.json | jq ' .paths["/api/checklists"] '
```

Expect to see a `post` operation.

- Swagger UI:

```
https://<API_HOST>/docs
```

Use the Try It Out buttons to confirm POST works.

---

## 9) Create a Checklist (POST)

Title is optional.

```bash
curl -v -X POST \
  -H "Content-Type: application/json" \
  -d '{}' \
  https://<API_HOST>/api/checklists
```

- Expected: 200 with JSON `{ id, title, status: "DRAFT", ... }`.
- Logs should show: `POST /api/checklists 200`.

---

## 10) Upload a PDF (to S3)

Prepare base64 (small PDF for the first test):

```bash
base64 -i sample.pdf | tr -d '\n' > pdf.txt
```

Upload:

```bash
curl -v -X POST \
  -H "Content-Type: application/json" \
  -d "$(jq -n --arg f sample.pdf --arg b "$(cat pdf.txt)" --arg ct "application/pdf" '{filename:$f, base64:$b, content_type:$ct}')" \
  https://<API_HOST>/api/checklists/<CHECKLIST_ID>/upload
```

- Expected: 200 with `DocumentOut` including `storage_key` (an S3 key, not a URL).

> Important: The API expects the PDF content as a base64 string in the JSON field `base64`. Do not upload the `.pdf` file itself or the `.txt` file. The `.txt` file is only a local convenience to hold the base64 string for curl/jq.

Confirm in detail view:

```bash
curl -s https://<API_HOST>/api/checklists/<CHECKLIST_ID> | jq
```

---

## 11) Process the Checklist (Anthropic)

Kick off processing:

```bash
curl -X POST https://<API_HOST>/api/checklists/<CHECKLIST_ID>/process
```

Poll until `status` becomes `READY` and items appear:

Option A — if `watch` is available:

```bash
watch -n 3 curl -s https://<API_HOST>/api/checklists/<CHECKLIST_ID> | jq
```

Option B — macOS-friendly loop (no `watch` required):

```bash
while true; do
  curl -s https://<API_HOST>/api/checklists/<CHECKLIST_ID> | jq
  sleep 3
done
```

Optional: install `watch` on macOS with Homebrew:

```bash
brew install watch
```

Troubleshooting:

- If status becomes `FAILED`, check `meta.error`.
- Verify `ANTHROPIC_API_KEY` and keep PDFs small for the first tests.

---

## 12) Web App: Pointing to the API

- Deploy the web app to Railway from `apps/web/`.
- Set an env like `NEXT_PUBLIC_API_BASE=https://<API_HOST>` (create if not present).
- In the web app code, call the API with:

```ts
await fetch(`${process.env.NEXT_PUBLIC_API_BASE}/api/checklists`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ title: "My first checklist" }),
});
```

- If CORS blocks browser calls, add your web origin to `ALLOWED_ORIGINS` in the API service.

---

## 13) Dependency Notes

- Python (API):
  - FastAPI, SQLAlchemy, psycopg[binary] (psycopg3), boto3, anthropic, httpx, python-dotenv
- Node (Web):
  - next 15.x, react 19.x

---

## 14) Logging and Verification

- API access logs will show the method and path actually received (e.g., `POST /api/checklists`). Use this to diagnose client issues.
- When debugging method issues, always test with curl or Swagger UI directly against the API host (not via web).

---

## 15) Appendix: Minimal .env examples

API `.env.example` key variables:

```
# Database
DATABASE_URL=postgresql+psycopg://user:pass@host:5432/db

# AWS S3
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=changeme
AWS_SECRET_ACCESS_KEY=changeme
S3_BUCKET=changeme

# Anthropic
ANTHROPIC_API_KEY=sk-ant-...
# Optional
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022

# Processing
LOCAL_SYNC_PROCESSOR=1

# CORS (add deployed web URL here)
ALLOWED_ORIGINS=https://your-web.up.railway.app

# Storage mocking (keep off for real S3)
# MOCK_STORAGE=0
```

---

## 16) Manage Checklist Items

List items for a checklist:

```bash
curl -s https://<API_HOST>/api/checklists/<CHECKLIST_ID>/items | jq
```

Patch a single item (partial update):

```bash
curl -s -X PATCH \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Updated item text",
    "category": "General",
    "priority": "HIGH",
    "order_index": 1,
    "completed": true
  }' \
  https://<API_HOST>/api/checklist-items/<ITEM_ID> | jq
```

Notes:

- `priority` must be one of `LOW`, `MEDIUM`, `HIGH`.
- `completed` is a boolean.
- Fields are optional; send only what you want to change.

---

## 17) Next Steps to Extend (Optional)

- Add delete endpoints for documents and items.
- Add better status transitions and progress metadata.
- Add file type validation and multi-file uploads.
- Add a simple web UI flow: Create → Upload → Process → Display items.

---

This guide will be updated as we iterate. Paste each section to your LLM in order to reproduce the setup, avoiding the known pitfalls above.

---

## 18) Web UI Implementation (Next.js 15, React 19, Tailwind, shadcn-style)

We added a minimal UI to exercise the API end-to-end.

What was added:

- Tailwind setup in `apps/web/`:
  - `tailwind.config.ts`
  - `postcss.config.js`
  - `app/globals.css` (imported in `app/layout.tsx`)
- Minimal shadcn-style UI primitives under `apps/web/app/_components/ui/`:
  - `button.tsx`, `input.tsx`, `label.tsx`
- Pages:
  - `apps/web/app/page.tsx` — redirects to `/checklists`
  - `apps/web/app/checklists/page.tsx` — Create → Upload (base64) → Process → Poll → Display & toggle items
    - Accepts `?cid=<CHECKLIST_ID>` to preselect an existing checklist
  - `apps/web/app/checklists/browse/page.tsx` — Lists all checklists and expands to show items inline
  - Both pages include top tabs (links) to switch between “Add Checklist” and “Browse Checklists”.

Environment

- Create `apps/web/.env` and set:
  - `NEXT_PUBLIC_API_BASE=https://<API_HOST>`
  - Restart Next.js dev server after changing `.env`.

Run locally (npm workspaces)

- From repo root (workspace root):
  ```bash
  npm i
  ```
- Start the web app:
  ```bash
  cd apps/web
  npm run dev
  ```
- Open:
  - http://localhost:3000/checklists (main UI)
  - http://localhost:3000/checklists/browse (list + inline items)

Notes on npm workspaces

- The repo uses npm workspaces via the root `package.json` with `"workspaces": ["apps/*"]`.
- Ensure the root `package.json` has a valid `version` (e.g., `0.0.0`). Without it, `npm i` can error: `Invalid Version:`.
- If you want to target only the web workspace:
  - `npm --workspace apps/web i` from the root, or
  - `npm i --workspaces=false` from `apps/web`.

Hydration warnings due to extensions

- Some password/notes manager extensions (e.g., NordPass) inject `data-np-*` attributes (e.g., `data-np-autofill-form-type`, `data-np-intersection-state`).
- These mutate the DOM and can trigger hydration mismatches. We mitigated by adding `suppressHydrationWarning` on main containers in pages.
- Alternative: test in an incognito window with extensions disabled, or render the form client-only.

UI usage flow

- On `/checklists`:
  - Create a checklist (optional title)
  - Upload a small PDF (base64)
  - Start processing and watch status move to READY
  - Toggle items as completed (PATCH)
- On `/checklists/browse`:
  - See all checklists from GET `/api/checklists`
  - Expand a row to fetch and show items via GET `/api/checklists/{id}/items`
  - Use the “Open” link to jump to `/checklists?cid=<id>`

### 18.1) Next.js Rewrites for API Proxy (No CORS)

We configured a rewrite so the web app can call its own `/api/...` endpoints while Next.js proxies the request to the FastAPI service server-side. This eliminates CORS problems entirely.

- File: `apps/web/next.config.mjs`
  - Uses `API_BASE` (fallbacks to `NEXT_PUBLIC_API_BASE`) and rewrites `/api/:path*` → `${API_BASE}/:path*`.
- Env:
  - In `apps/web/.env`:
    - `API_BASE=https://<YOUR_FASTAPI_HOST>`
  - Restart the dev server after changing env.
- Client code (browser) only calls same-origin `/api/...`.
- Note: If route handlers exist under `app/api/`, they take precedence over rewrites. Either remove them or let them co-exist; both approaches avoid CORS. We currently favor rewrites for simplicity.

### 18.2) Checklist Detail Page `/checklists/[id]`

- Added a dedicated detail page at `apps/web/app/checklists/[id]/page.tsx`.
- Capabilities:
  - Rename checklist title (PATCH `/api/checklists/{id}`)
  - Delete checklist (DELETE `/api/checklists/{id}`) with a confirmation dialog
  - View checklist items (read-only)
- UI:
  - Minimal confirm dialog component: `apps/web/app/_components/ui/confirm-dialog.tsx`
  - Lightweight in-page toasts for success/error messages (no extra deps)
- Navigation:
  - The browse list now links to `/checklists/{id}` (replaces the previous `?cid=` usage)

### 18.3) Notes on Rewrites vs. Route Handlers

- We rely on Next.js `rewrites` to proxy browser calls from `/api/:path*` to `${API_BASE}/api/:path*`.
- Important: Any files placed under `apps/web/app/api/**` will override rewrites for matching paths.
  - If you are using rewrites, avoid creating empty route handler files (no exported methods), as they will shadow rewrites and produce 404s.
  - Either remove those files or implement the handlers; otherwise, keep the rewrites-only approach.

### 18.4) Interactive Item Toggling

- The checklist detail page (`apps/web/app/checklists/[id]/page.tsx`) now supports toggling items complete/incomplete.
- API: `PATCH /api/checklist-items/{item_id}` with JSON `{ completed: boolean }`.
- UX:
  - Checkbox disables while the request is in-flight.
  - Optimistic UI update on success.
  - Success/error toasts using a lightweight in-page toast component (no extra deps).
- Caution with rewrites:
  - Ensure there are no empty `app/api/**` files shadowing these paths, or the rewrite will not apply and you may see 404s.

### 18.6) Browse Page: Client-side Search

- The browse page (`apps/web/app/checklists/browse/page.tsx`) now includes a basic client-side search box.
- Filters the in-memory list by `title`, `id`, or `status` as you type.
- No backend changes required. Works with the existing fetch from `/api/checklists`.

### 18.7) Browse Page: Inline Items Removed

- We removed the inline items accordion from the browse page.
- Items are now viewed on the dedicated detail route: `/checklists/[id]`.
- The "Open" action on each row navigates to the detail page.

### 18.8) Rewrites Gotcha and Fix

- The Next.js rewrite must proxy to the upstream API prefix.
- Ensure `apps/web/next.config.mjs` maps:
  - `source: '/api/:path*'` → `destination: `${API_BASE}/api/:path\*``
- If you omit `/api` in the destination, calls like `/api/checklists` will 404 upstream (they would hit `/<path*>` instead of `/api/<path*>`).

### 18.9) UI Note: Button Variant Backgrounds

- We adjusted styles so variant backgrounds (e.g., `destructive`) are not overridden by the base `.btn` class.
- Fix applied by moving the background color out of the base `.btn` class and into specific variants in `app/_components/ui/button.tsx`.
- Result: `<Button variant="destructive">` renders with red background consistently.

### 18.10) Detail Page: Status and Steps

- Components:
  - `apps/web/app/_components/ui/status-pill.tsx`
  - `apps/web/app/_components/ui/step-indicator.tsx`
- Integrated into `apps/web/app/checklists/[id]/page.tsx` Overview section to reflect current checklist status and its step (DRAFT/UPLOADING/PROCESSING/READY/FAILED).

### 18.11) Detail Page: Progress Overview and Category Grouping

- Progress overview: completed vs total with a progress bar.
- Category grouping: items grouped by `category` with per-category completed counts.
- Ordering: within each category, items are sorted by `order_index` (if present) then by `id`.
- Location: `apps/web/app/checklists/[id]/page.tsx` in the Items section.

### 18.12) Global Toaster (Provider + Hook)

- Components:
  - `apps/web/app/_components/ui/toaster.tsx` — `ToasterProvider` and `useToast()`
  - Wired at root: `apps/web/app/layout.tsx` wraps the app with `<ToasterProvider>`
- Usage:
  - In client components, import `useToast` and call `push('success'|'error'|'info', message)`.
  - Toasts render globally in the bottom-right corner.

## 19) Roadmap and Acceptance Criteria (to reach parity and beyond)

This section tracks what is implemented and what remains, with clear acceptance criteria for each item.

### 19.1) Frontend (Next.js App Router)

- [Done] Dedicated checklist detail page: `apps/web/app/checklists/[id]/page.tsx`

  - Can rename checklist (PATCH)
  - Can delete checklist (DELETE) with confirm dialog
  - Shows items and supports toggling complete/incomplete (PATCH)

- [Done] Rewrites-based proxy (no CORS): `apps/web/next.config.mjs`

  - `/api/:path*` → `${API_BASE}/api/:path*`

- [Done] Browse page search: `apps/web/app/checklists/browse/page.tsx`

  - Client-side filter by title/id/status

- [Done] Remove inline items accordion on browse

  - Navigate to `/checklists/[id]` instead

- [Done] Detail page polish
  - Status pill and basic step indicator for DRAFT/UPLOADING/PROCESSING/READY/FAILED
  - Progress overview (completed/total + bar)
  - Group items by category with per-category counts

- [Done] Global toaster component under `app/_components/ui`

  - Replace page-local toasts for consistency
  - Any page can push success/error/info toasts via a small API

- [Planned] SSR initial data fetches

  - `/checklists/browse`: list fetched server-side
  - `/checklists/[id]`: base detail fetched server-side (client hydrates actions)
  - Acceptance: first paint contains data without a client-side loading flash

- [Planned] Browse improvements

  - Server-side search/filter support (if API provides query params)
  - Sorting (updated_at/title/status) and basic pagination
  - Acceptance: UI controls update the list, URL params reflect state; no full reload needed

- [Optional/Planned] Upload UX parity (if required by assignment)
  - Multi-file upload zone with thumbnails, progress, and auto-start processing
  - Acceptance: files show progress, checklist status updates accordingly; process start triggers status change

### 19.2) Backend/API (FastAPI)

- [Verify] Endpoints in use by UI

  - `GET /api/checklists` — browse
  - `GET /api/checklists/{id}` — detail
  - `GET /api/checklists/{id}/items` — items (fallback if not embedded)
  - `PATCH /api/checklists/{id}` — rename
  - `DELETE /api/checklists/{id}` — delete
  - `POST /api/checklists/{id}/upload` — pdf upload
  - `POST /api/checklists/{id}/process` — start processing
  - `PATCH /api/checklist-items/{item_id}` — toggle completed
  - Acceptance: each route returns 2xx with correct shapes as used in the UI

- [Optional] Server-side search/filter support
  - `GET /api/checklists?q=...&status=...&sort=...&page=...`
  - Acceptance: returns filtered, sorted, paginated lists with stable shape

### 19.3) Infra and configuration

- [Done] Same-origin proxy via rewrites; `.env` uses `API_BASE` host
- [Done] Avoid route handlers shadowing rewrites (remove empty `app/api/**` files)
- [Planned] Add minimal e2e verification steps to CI (optional)

## 20) Reproducibility Checklist (for another LLM/operator)

Follow these steps to reproduce the working setup:

1. Web env

   - File: `apps/web/.env`
   - Set `API_BASE=https://<YOUR_FASTAPI_HOST>` (no trailing slash)

2. Rewrites

   - File: `apps/web/next.config.mjs`
   - Ensure rewrites:
     - `source: '/api/:path*'` → `destination: `${API_BASE}/api/:path\*``

3. No route handler shadowing

   - Ensure no empty files under `apps/web/app/api/**` for paths you expect to proxy

4. Start dev server

   - `cd apps/web && npm run dev`

5. Verify

   - `curl -s http://localhost:3000/api/checklists | jq` should return a list
   - In browser, visit `/checklists/browse` and `/checklists/[id]`

6. Feature checks

   - Rename works (PATCH)
   - Delete shows confirm dialog and works (DELETE)
   - Item checkbox toggles completion (PATCH), with toasts
   - Toaster visible globally (no page-local toasts needed)
   - Browse search filters client-side by title/id/status

7. Optional polish (if implementing next)
   - Add progress overview/grouping on detail page
   - SSR the initial fetches for faster first paint

Note: The layout (`apps/web/app/layout.tsx`) wires the `ToasterProvider` to enable global toasts.
