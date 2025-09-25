# Forgent Checklist - AI-Powered Document Processing

An AI-powered document processing application that generates actionable checklists from uploaded PDF tender documents. The system uses Anthropic's Claude API for document analysis, question answering, and condition evaluation.

## Architecture

- **Frontend**: Next.js 15 (TypeScript) - `apps/web/`
- **API**: FastAPI (Python) - `services/api/`
- **Worker**: Dramatiq + Redis (Python) - `services/worker/`
- **Storage**: AWS S3 compatible
- **Database**: PostgreSQL
- **AI**: Anthropic Claude (File API + structured outputs)

## Features

- Upload multiple PDF tender documents
- Define custom questions and conditions for evaluation
- Automatic document processing using Anthropic's File API
- Structured checklist generation with requirements extraction
- Question answering and boolean condition evaluation
- Real-time processing status updates
- Modern, responsive web interface

## Prerequisites

- **Python 3.11.x** (required for PyMuPDF compatibility)
- **Node.js 20+** with npm/pnpm
- **uv** package manager (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- **Redis** server (for job queue)
- **PostgreSQL** database
- **Anthropic API key**
- **AWS S3** bucket (or compatible storage)

## Quick Start

### 1. Clone and Setup

```bash
git clone <repository-url>
cd forgent-checklist
```

### 2. Environment Configuration

Create `.env` files for each service (these are gitignored):

#### `services/api/.env`

```bash
# Database
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/forgent

# Redis Queue
REDIS_URL=redis://localhost:6379/0

# Anthropic AI
ANTHROPIC_API_KEY=sk-ant-api03-your-key-here

# AWS S3 Storage
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
S3_BUCKET=your-bucket-name

# Worker Integration
WORKER_INGEST_TOKEN=your-shared-secret-token
```

#### `services/worker/.env`

```bash
# Redis Queue
REDIS_URL=redis://localhost:6379/0

# Anthropic AI
ANTHROPIC_API_KEY=sk-ant-api03-your-key-here
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022
ANTHROPIC_REPAIR_MODEL=claude-3-haiku-20240307

# API Integration
API_BASE=http://localhost:8000
WORKER_INGEST_TOKEN=your-shared-secret-token

# AWS S3 Storage
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
S3_BUCKET=your-bucket-name
```

#### `apps/web/.env.local`

```bash
# API Proxy
NEXT_PUBLIC_API_BASE=http://localhost:8000
```

### 3. Start Infrastructure Services

#### Redis (using Docker)

```bash
docker run --rm -p 6379:6379 redis:7
```

#### PostgreSQL (using Docker)

```bash
docker run --rm -p 5432:5432 \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=forgent \
  postgres:16
```

### 4. Install Dependencies

#### API Service

```bash
cd services/api
uv sync
```

#### Worker Service

```bash
cd services/worker
uv sync
```

#### Web Frontend

```bash
cd apps/web
npm install
```

### 5. Start Application Services

#### API Server (Terminal 1)

```bash
cd services/api
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

#### Worker Process (Terminal 2)

```bash
cd services/worker
uv run dramatiq worker.main --processes 1 --threads 1
```

#### Web Frontend (Terminal 3)

```bash
cd apps/web
npm run dev
```

### 6. Access the Application

- **Web Interface**: http://localhost:3000
- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

## Usage Workflow

1. **Create a Checklist**: Navigate to the web interface and create a new checklist
2. **Upload Documents**: Add PDF tender documents to your checklist
3. **Configure Questions**: Define questions you want answered from the documents
4. **Set Conditions**: Create boolean conditions for evaluation (e.g., "Is the deadline before 2025?")
5. **Process Documents**: Trigger processing - the worker will:
   - Upload PDFs to Anthropic's File API
   - Extract structured requirements
   - Answer your questions
   - Evaluate conditions as true/false
   - Generate a comprehensive checklist
6. **Review Results**: View the generated checklist with answers, evaluations, and evidence

## Example Questions & Conditions

Based on the TASK.md requirements:

### Questions

- "In welcher Form sind die Angebote/Teilnahmeanträge einzureichen?" (In what form should offers/applications be submitted?)
- "Wann ist die Frist für die Einreichung von Bieterfragen?" (When is the deadline for submitting bidder questions?)

### Conditions

- "Ist die Abgabefrist vor dem 31.12.2025?" (Is the application deadline before 31.12.2025?)

## Development

### Project Structure

```
forgent-checklist/
├── apps/web/                 # Next.js frontend
│   ├── app/                  # App router pages
│   ├── components/           # React components
│   └── public/              # Static assets
├── services/api/            # FastAPI backend
│   ├── app/                 # Application code
│   ├── pyproject.toml       # Dependencies
│   └── uv.lock             # Lockfile
├── services/worker/         # Dramatiq worker
│   ├── worker/              # Worker modules
│   ├── pyproject.toml       # Dependencies
│   └── uv.lock             # Lockfile
└── README.md               # This file
```

### Key Components

- **Document Processing**: Anthropic File API integration for PDF analysis
- **Question Answering**: Structured prompts for extracting specific information
- **Condition Evaluation**: Boolean logic evaluation with confidence scoring
- **Checklist Generation**: Automated requirement extraction and categorization
- **Real-time Updates**: WebSocket-like status updates via polling

### API Endpoints

- `POST /api/checklists` - Create new checklist
- `GET /api/checklists/{id}` - Get checklist details
- `POST /api/checklists/{id}/documents` - Upload documents
- `POST /api/checklists/{id}/process` - Trigger processing
- `GET /api/checklists/{id}/prompts` - Get questions/conditions
- `POST /api/prompt-templates` - Manage reusable prompts

## Troubleshooting

### Common Issues

1. **PyMuPDF Installation Fails**

   - Ensure you're using Python 3.11.x (PyMuPDF doesn't support 3.13 yet)
   - Use `pyenv` to manage Python versions if needed

2. **API Requests Return 404**

   - Check that `NEXT_PUBLIC_API_BASE` is set in `apps/web/.env.local`
   - Restart the Next.js dev server after changing environment variables
   - Verify the API server is running on port 8000

3. **Worker Not Processing Jobs**

   - Ensure Redis is running and accessible
   - Check that `REDIS_URL` matches in both API and worker environments
   - Verify `WORKER_INGEST_TOKEN` is identical in both services

4. **Anthropic API Errors**
   - Verify your API key is valid and has sufficient credits
   - Check rate limits if you're seeing 429 errors
   - Ensure file uploads are within Anthropic's size limits

### Logs and Debugging

- API logs: Check the uvicorn console output
- Worker logs: Monitor the dramatiq worker console
- Frontend: Use browser developer tools for client-side issues
- Database: Check PostgreSQL logs for connection issues

## Deployment

For production deployment, consider:

- Use environment-specific configuration
- Set up proper logging and monitoring
- Configure SSL/TLS certificates
- Use a production WSGI server (gunicorn)
- Set up database migrations
- Configure Redis persistence
- Use a CDN for static assets

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

[Add your license information here]
