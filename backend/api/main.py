"""
backend/api/main.py
Minimal FastAPI entry-point.  Run with:
    uvicorn backend.api.main:app --reload

This file will grow to host /ingest, /cluster, /layout endpoints once both
spikes are validated.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Parallax API", version="0.1.0")

# Allow the Vite dev server (localhost:5173) to hit the API during development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def health_check():
    """Quick liveness probe — returns OK so you can confirm the server started."""
    return {"status": "ok", "project": "Parallax", "api_version": "0.1.0"}
