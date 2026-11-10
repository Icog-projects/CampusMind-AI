"""
CampusMind AI – Backend Entry Point
FastAPI application with a basic health check endpoint.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="CampusMind AI API",
    description="Backend API for the CampusMind AI student assistant platform.",
    version="0.1.0",
)

# Allow requests from the local React dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["Health"])
def health_check():
    """Returns the operational status of the API."""
    return {"status": "ok", "service": "CampusMind AI API"}
