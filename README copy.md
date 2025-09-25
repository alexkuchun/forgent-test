# Forgent Checklist (Next.js + FastAPI + Worker)

An AI-powered document processing app that generates actionable checklists from uploaded PDFs. This implementation mirrors the original flows but uses Python for backend + worker.

## Stack

- Frontend: Next.js (apps/web)
- Backend API: FastAPI (services/api)
- Worker: Dramatiq (services/worker)
- Storage: S3 (planned)
- DB: Postgres (Railway or Neon; planned)
- LLM & OCR: Anthropic Claude (Claude-only OCR)

## Local Development

- Web
  - cd apps/web
  - npm install
  - npm run dev
  - http://localhost:3000
- API
  - cd services/api
  - uv sync
  - uv run uvicorn app.main:app --reload --port 8000
  - http://localhost:8000/health
- Worker
  - cd services/worker
  - uv sync
  - export REDIS_URL=... # (Upstash or local)
  - uv run dramatiq worker.main --processes 1 --threads 1

## Env Vars

See `.env.example` files under each service. Minimum:

- services/api
  - DATABASE_URL=postgresql+psycopg://user:pass@host:port/db
  - AWS_REGION=...
  - AWS_ACCESS_KEY_ID=...
  - AWS_SECRET_ACCESS_KEY=...
  - S3_BUCKET=...
  - ANTHROPIC_API_KEY=...
- services/worker
  - REDIS_URL=...
  - ANTHROPIC_API_KEY=...
  - AWS\_... (if reading from S3)

## Next Steps

- Implement FastAPI endpoints matching the original API.
- Wire S3 uploads (base64 → S3) and document rows.
- Implement worker pipeline: download → Claude OCR → Claude checklist → persist → update status.
- Connect web UI to API.
