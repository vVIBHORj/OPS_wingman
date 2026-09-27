# OpsWingman — Local Development Guide

This guide provides step-by-step instructions for running and developing OpsWingman locally in Phase 0 and beyond.

---

## 1. Prerequisites

Ensure you have the following installed on your development machine:
- **Docker Engine** (v24.0+) & **Docker Compose** (v2.20+)
- **Python** (3.12 or newer recommended)
- **Node.js** (v20 LTS recommended) & **npm** (v10+)
- **Git**

---

## 2. Environment Configuration

1. In the repository root, copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
2. Review the default values in `.env`. The defaults are pre-configured to work out-of-the-box with local Docker services.

---

## 3. Starting Infrastructure Services (Docker)

OpsWingman uses Docker Compose to run local infrastructure dependencies:
- **PostgreSQL 16 + pgvector** (Operational storage & vector search)
- **Valkey** (Redis-compatible queue, state store, and cache)
- **Mailpit** (Local SMTP server & web UI for email testing)
- **Langfuse** (Self-hosted trace and evaluation dashboard)

To start the infrastructure services:
```bash
docker compose up -d postgres valkey mailpit langfuse-db langfuse
```

### Inspect Service Status:
```bash
docker compose ps
```

### Access Local Service Portals:
- **PostgreSQL**: `localhost:5432` (User: `postgres`, Password: `postgres`, DB: `opswingman`)
- **Valkey**: `localhost:6379`
- **Mailpit Web UI**: [http://localhost:8025](http://localhost:8025)
- **Langfuse Web UI**: [http://localhost:3001](http://localhost:3001)

---

## 4. Running the Backend Service

1. Create and activate a Python virtual environment:
   ```bash
   # Windows PowerShell:
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1

   # Linux / macOS:
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. Install backend dependencies:
   ```bash
   pip install -r backend/requirements.txt
   ```

3. Launch the FastAPI development server:
   ```bash
   uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
   ```

4. Verify backend status:
   - Root endpoint: [http://localhost:8000/](http://localhost:8000/)
   - Health check: [http://localhost:8000/health](http://localhost:8000/health)
   - Interactive OpenAPI docs: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 5. Running the Frontend Service

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```

2. Install frontend dependencies:
   ```bash
   npm install
   ```

3. Start the Next.js development server:
   ```bash
   npm run dev
   ```

4. Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## 6. Running Tests

Execute pytest from the root repository directory:
```bash
pytest
```

To run only unit tests:
```bash
pytest tests/unit
```

---

## 7. Stopping Services

To stop all background Docker containers:
```bash
docker compose down
```

To stop containers and wipe persistent database volumes (useful for clean-slate resets):
```bash
docker compose down -v
```
