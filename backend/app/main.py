"""LayerLens backend entrypoint."""
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .routers import analyze, graph, health

app = FastAPI(title="LayerLens API", version="0.2.0")

cors_origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", "*").split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True if "*" not in cors_origins else False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(graph.router)
app.include_router(analyze.router)

# Serve the built frontend from the same origin so a single container
# and port exposes the entire full-stack app.
DIST_CANDIDATES = [
    os.environ.get("FRONTEND_DIST"),
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")),
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")),
    os.path.abspath(os.path.join(os.path.dirname(__file__), "dist")),
    "/srv/frontend/dist",
    "/app/frontend/dist",
]
DIST = next((d for d in DIST_CANDIDATES if d and os.path.isdir(d)), None)

if DIST and os.path.isdir(DIST):
    assets_dir = os.path.join(DIST, "assets")
    if os.path.isdir(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        candidate = os.path.join(DIST, path)
        if path and os.path.isfile(candidate):
            return FileResponse(candidate)
        return FileResponse(os.path.join(DIST, "index.html"))
