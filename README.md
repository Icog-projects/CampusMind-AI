# CampusMind AI

AI-powered student assistant platform built with FastAPI (backend) and React + Vite + Tailwind CSS (frontend).

---

## Project Structure

```
CampusMind-AI/
├── backend/           # Python + FastAPI
│   ├── main.py
│   ├── requirements.txt
│   ├── .env.example
│   └── venv/          # Git-ignored
├── frontend/          # React + Vite + Tailwind CSS
│   ├── src/
│   ├── index.html
│   └── ...
├── docs/              # Project Documentation & Specifications
│   ├── CampusMind-AI.pdf                 # SRS Version 1.2
│   └── CampusMind_AI_SRS_Version_1.3.pdf # SRS Version 1.3
├── .gitignore
└── README.md
```

---

## Prerequisites

- Python 3.12+ (3.13 also works for initial setup)
- Node.js v18+ (LTS)
- Git

---

## Backend Setup

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
```

### Run the backend

```bash
# From the backend/ directory, with venv activated
uvicorn main:app --reload --port 8000
```

API will be available at: http://localhost:8000
Health check: http://localhost:8000/health
API docs: http://localhost:8000/docs

---

## Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Frontend will be available at: http://localhost:5173

---

## Environment Variables

Copy `backend/.env.example` to `backend/.env` and fill in the required values before running in production.

---

## Status

> Initial scaffold complete. Application features not yet implemented.
