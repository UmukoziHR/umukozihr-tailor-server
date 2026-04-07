# UmukoziHR Resume Tailor - Backend API v2.5

🚀 **AI-Powered Resume Tailor + CareerOps Job Pipeline**

FastAPI backend that tailors resumes/cover letters with Gemini AI **and** runs a full CareerOps job pipeline: scanning 20+ company portals, scoring every role with a 6-block AI evaluation, pre-filling application forms, and tracking submissions — all with human-in-the-loop confirmation before anything is submitted.

## ✨ Features

### Core (v1.x)
- 🤖 **AI Document Generation** — Gemini 2.5 Flash for tailored resumes & cover letters
- 📄 **LaTeX → PDF Compilation** — Local latexmk + Docker fallback
- 🔐 **JWT Authentication** — Secure auth with bcrypt
- 📊 **Multi-Format Resumes** — US, EU, and Global layouts
- 🎯 **ATS Optimization** — Keyword injection and formatting

### CareerOps Pipeline (v2.5)
- 🔍 **Portal Scanner** — Scans 20+ company Greenhouse & Ashby boards for new roles
- ⚡ **6-Block Evaluation** — AI scores each job on CV match, north-star alignment, compensation, culture, and STAR readiness
- 📋 **Apply Queue** — Pre-fills application form fields; requires human approval before submit
- 📈 **Tracker** — Full pipeline stats and submission history board
- 🤖 **Playwright Integration** — Headless Chromium for JavaScript-heavy portals

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Framework | FastAPI 0.104+ |
| AI/LLM | Google Gemini 2.5 Flash |
| Database | PostgreSQL (SQLAlchemy async) |
| Authentication | JWT + bcrypt |
| Document Gen | LaTeX + Jinja2 templates |
| Portal Scanning | httpx + Greenhouse API + Playwright (Chromium) |
| JD Extraction | Greenhouse API → httpx + BeautifulSoup → Playwright |

## 📋 Prerequisites

- Python 3.11+
- PostgreSQL (or `DATABASE_URL=sqlite:///./app.db` for dev)
- Google Gemini API key ([Get one here](https://ai.google.dev/))
- Playwright Chromium (installed automatically by `requirements.txt`)

## 🚀 Quick Start

### 1. Install Dependencies
```bash
cd server
python -m venv venv
source venv/bin/activate      # macOS/Linux
# OR
venv\Scripts\activate         # Windows

pip install -r requirements.txt

# Install Playwright's Chromium browser
python -m playwright install chromium
```

### 2. Configure Environment
Create a `.env` file in the `server/` directory:
```env
# Required
GEMINI_API_KEY=your_gemini_api_key_here
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/umukozihr
# or for local dev:
DATABASE_URL=sqlite+aiosqlite:///./app.db

# Auth
SECRET_KEY=your-secret-key-change-in-production
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Optional LLM tuning
GEMINI_MODEL=gemini-2.5-flash
GEMINI_MAX_OUTPUT_TOKENS=8192
GEMINI_THINKING_BUDGET=0
```

### 3. Initialize Database
```bash
python migrate.py
```

### 4. Start the Server
```bash
# Development (with auto-reload)
set -a && source .env && set +a  # load env vars first
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# If port 8000 is taken
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

Server docs: **http://localhost:8000/docs**

## 📡 API Endpoints

### Health
```http
GET /health
```

### Authentication
```http
POST /api/v1/auth/signup
POST /api/v1/auth/login
```

### Profile & Generation (v1.x)
```http
POST /api/v1/profile/profile
POST /api/v1/generate/generate
GET  /api/v1/generate/status/{id}
GET  /artifacts/{filename}
```

### Portal Configuration (v2.5)
```http
GET  /api/v1/portals/config         # Get active portal list
POST /api/v1/portals/config         # Save portal configuration
```

### Job Scanner (v2.5)
```http
POST /api/v1/scanner/scan                      # Trigger portal scan (background)
GET  /api/v1/scanner/scan/status               # Poll scan progress
GET  /api/v1/scanner/jobs                      # List discovered jobs (limit/offset/status/company)
POST /api/v1/scanner/jobs/{id}/evaluate        # AI-evaluate a specific job
POST /api/v1/scanner/jobs/{id}/dismiss         # Dismiss a job
```

### Apply Queue (v2.5)
```http
POST   /api/v1/apply/queue/{job_id}           # Add evaluated job to apply queue
GET    /api/v1/apply/queue                    # List queued applications
GET    /api/v1/apply/queue/{id}/form-fields   # Get pre-filled form fields
POST   /api/v1/apply/queue/{id}/confirm       # Mark as submitted (human confirms)
DELETE /api/v1/apply/queue/{id}               # Remove from queue
```

### Pipeline Stats (v2.5)
```http
GET /api/v1/pipeline/stats
```

## 🔬 Pipeline Architecture

```
Scanner Layer  →  Evaluation Layer  →  Apply Queue  →  Tracker
─────────────     ────────────────     ────────────     ───────
Greenhouse API    Gemini 6-block AI    Pre-fill forms   Stats
Ashby scrape      CV match score       Human approval   History
Playwright        North-star score     Confirm/reject
                  Comp score
                  Cultural score
                  STAR stories
```

**Key design decisions:**
- **Never auto-submits**: Every application requires explicit human confirmation
- **Greenhouse API preferred**: Direct REST API gives clean JSON + HTML; avoids Playwright for those portals
- **HTML entity decoding**: Greenhouse's `content` field returns `&lt;div&gt;` — must call `html.unescape()` before BeautifulSoup
- **Ashby `__NEXT_DATA__`**: Ashby boards are SPAs; scraping the embedded JSON in the page's `<script id="__NEXT_DATA__">` is more reliable than Playwright DOM traversal
- **Windows Playwright fix**: `asyncio.WindowsProactorEventLoopPolicy()` must be set before launching Chromium on Windows (default SelectorEventLoop doesn't support subprocess creation)

## 📁 Project Structure

```
server/
├── app/
│   ├── main.py                   # FastAPI app, router registration
│   ├── models.py                 # Pydantic request/response models
│   ├── auth/
│   │   └── auth.py               # JWT + bcrypt authentication
│   ├── core/
│   │   ├── llm.py                # Gemini LLM client
│   │   ├── tailor.py             # Resume tailoring logic
│   │   ├── tex_compile.py        # LaTeX → PDF compilation
│   │   ├── job_scanner.py        # Portal scanner (Greenhouse + Ashby + Playwright)
│   │   └── evaluator.py          # 6-block job evaluation
│   ├── db/
│   │   ├── database.py           # Async SQLAlchemy setup
│   │   └── models.py             # ORM models (users, discovered_jobs, job_evaluations, application_queue)
│   ├── routes/
│   │   ├── v1_auth.py            # Auth endpoints
│   │   ├── v1_profile.py         # Profile endpoints
│   │   ├── v1_generate.py        # Document generation
│   │   ├── v1_scanner.py         # Job scanner + discovery endpoints
│   │   ├── v1_apply.py           # Apply queue endpoints
│   │   └── v1_pipeline.py        # Pipeline stats
│   └── templates/                # LaTeX resume templates
├── tests/
├── artifacts/                    # Generated PDFs/TEX files
├── migrate.py                    # DB migration runner
├── start.sh                      # Production entrypoint
├── Dockerfile                    # Docker image (includes TexLive + Playwright)
└── requirements.txt
```

## 🐳 Docker

The Dockerfile includes full TeX Live (~2GB) and Playwright Chromium:

```bash
# Build
docker build -t umukozihr-server .

# Run
docker run -p 8000:8000 \
  -e GEMINI_API_KEY=your_key \
  -e DATABASE_URL=postgresql+asyncpg://... \
  umukozihr-server
```

Works with AWS App Runner and ECS out of the box.

## 🧪 Testing

```bash
python tests/run_all_tests.py          # Full suite
python tests/test_components.py        # Unit tests
python tests/test_api.py               # API integration tests
python tests/full_api_test.py          # End-to-end
```

## 🐛 Troubleshooting

| Problem | Fix |
|---------|-----|
| `ModuleNotFoundError: PIL` | `pip install pillow` |
| `ModuleNotFoundError: jwt` | `pip install PyJWT` |
| Playwright `NotImplementedError` on Windows | Set `asyncio.WindowsProactorEventLoopPolicy()` before launch |
| Greenhouse API 404 | Verify `api_slug` matches exact board slug (e.g. `anthropic` not `anthropic-ai`) |
| Server loads old `.pyc` after edits | `find . -name "*.pyc" -delete` and restart |
| Port 8000 in use (Windows) | Use port 8001; kill old process via `taskkill /F /PID <n>` in cmd.exe |

## 🔒 Security

- JWT authentication on all pipeline endpoints
- CORS protection
- Input validation via Pydantic
- Never auto-submits applications — human confirmation required

## 📊 Performance Notes

- **Portal scan**: ~433 jobs from 20 companies in under 60 seconds (Greenhouse API is fast; Playwright is slow)
- **JD extraction**: ~5-15 seconds per job (Greenhouse API instant; Playwright ~10s)
- **Evaluation**: ~8-20 seconds per job (Gemini 2.5 Flash)
- **Concurrent users**: Multiple simultaneous requests supported

## 📝 API Documentation

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

---

**Built by the UmukoziHR Team** · Private — Internal Use
