[**Read Project Report**](docs/REPORT.md)

# CampusMind AI

CampusMind AI is a university knowledge assistant that gives students and staff
verifiable answers from institutional documents. It combines hybrid retrieval,
grounded generation, and exact and semantic answer caching.

## Overview

CampusMind AI addresses the difficulty of finding reliable information across
handbooks, syllabi, policies, and facility guides. Administrators upload source
documents, while authenticated users ask questions through a React web
interface. Answers include inline citations to the retrieved passages, and
insufficient evidence produces a clear not-found response instead of an
unsupported answer.

### Key features

- PDF, DOCX, and TXT extraction and indexing
- Fixed, recursive, and semantic chunking strategies
- Hybrid BM25 and Qdrant vector retrieval
- Reciprocal Rank Fusion (RRF) and Cross-Encoder reranking
- Grounded Groq LLM responses with source citations
- Redis exact answer caching and Qdrant-backed semantic caching
- JWT authentication with student, staff, and admin roles
- Conversation history, document management, health checks, and cache metrics

## Architecture and workflow

### Document ingestion

1. An administrator uploads a supported document.
2. The backend extracts text and preserves document and page metadata.
3. The selected chunking strategy splits the text.
4. BGE-small embeddings and BM25 indexes are generated.
5. Chunks and metadata are stored in Qdrant for retrieval.

### Question answering

1. The API checks Redis for an exact, normalized question key.
2. On a miss, the query is embedded and searched with BM25 and Qdrant.
3. RRF combines the rankings, followed by Cross-Encoder reranking.
4. The Groq model generates an answer constrained by retrieved evidence.
5. Grounded answers are cached in Redis and indexed for semantic matching.

Redis stores complete serialized answers and citations. Qdrant stores document
chunks and semantic-cache metadata; it does not store answer payloads. Scope and
knowledge-base version filters prevent inappropriate semantic matches.

## Technology stack

| Area | Technologies |
| --- | --- |
| Backend | Python 3.12+, FastAPI, Uvicorn, Pydantic |
| Retrieval | Qdrant, BM25Okapi, RRF, sentence-transformers |
| Generation | Groq Cloud (`openai/gpt-oss-120b`) |
| Storage and caching | MySQL, SQLAlchemy, Redis |
| Frontend | React 18, Vite, Tailwind CSS |
| Security | JWT, Passlib/Bcrypt, role-based access control |

## Project structure

```text
CampusMind-AI/
├── backend/
│   ├── app/
│   │   ├── api/             # FastAPI routes
│   │   ├── core/            # Configuration, database, and security
│   │   ├── repositories/    # Database access
│   │   └── services/        # Ingestion, retrieval, RAG, and caching
│   ├── evaluation/          # Benchmark and metric utilities
│   └── tests/               # Backend tests
├── frontend/
│   └── src/                 # React application
└── docs/
    └── REPORT.md           # Concise technical evaluation report
```

## Setup

### Prerequisites

- Python 3.12+
- Node.js and npm
- Docker
- MySQL, Redis, and Qdrant
- A Groq API key

### Supporting services

From the project directory, start Redis and Qdrant using Docker. Ensure MySQL
is running and create the `campusmind` database.

```powershell
docker run -d --name campusmind-redis -p 6379:6379 redis:7
docker run -d --name campusmind-qdrant -p 6333:6333 qdrant/qdrant
```

### Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Update `backend/.env` with the Groq, MySQL, Redis, and Qdrant settings. At
minimum, configure `GROQ_API_KEY`, `DATABASE_URL` (or the MySQL components),
`REDIS_URL`, `QDRANT_URL`, and a secure `JWT_SECRET`.

### Frontend

```powershell
cd frontend
npm install
```

## Run the application

Start the backend from `backend`:

```powershell
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Start the frontend from `frontend` in a second terminal:

```powershell
npm run dev
```

- Web application: `http://localhost:5173`
- API: `http://localhost:8000`
- Swagger UI: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health`

## Main API routes

| Method | Route | Purpose |
| --- | --- | --- |
| `POST` | `/auth/register` | Register a user |
| `POST` | `/auth/login` | Issue access and refresh tokens |
| `POST` | `/documents/upload` | Admin document ingestion |
| `GET` | `/documents` | List uploaded documents |
| `POST` | `/chat/ask` | Ask a grounded question |
| `GET` | `/chat/sessions` | List conversation sessions |
| `GET` | `/chat/history/{id}` | Read conversation history |
| `GET` | `/health` | Check service connectivity |
| `GET` | `/metrics/cache` | View cache telemetry |

Protected routes require an access token in the `Authorization` header.

## Testing

From `backend` with the virtual environment activated:

```powershell
pytest tests/ -v
```

The existing suite reports **122/122 tests passing** across authentication,
document extraction, chunking, retrieval, caching, persistence, generation,
and API workflows. Benchmark methodology and measured results are documented
in the [project report](docs/REPORT.md).

## Design highlights

- **Cache-aside** keeps cache orchestration in the API, allowing grounding
  validation before an answer is cached and fail-soft behavior when Redis is
  unavailable.
- **RRF** combines BM25 and dense rankings without comparing incompatible raw
  score scales.
- **Versioned semantic-cache metadata** isolates cached answers by access scope
  and knowledge-base version without requiring mass key deletion.
- **Grounding protection** prevents unsupported answers from entering either
  cache.

## Limitations and future work

The current benchmark uses an in-memory Qdrant collection and a controlled LLM
harness for reproducibility. Production deployments should continue validating
retrieval quality on a larger, evolving institutional corpus and monitor
external model latency, cost, and answer quality.
