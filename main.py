"""Pixel Labs Network Builder - Main FastAPI Application."""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from database import init_db, get_stats
from router import router as api_router
from config import APP_HOST, APP_PORT


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    init_db()
    yield


app = FastAPI(
    title="Pixel Labs Network Builder",
    description="Professional Network Research + Recommendation Assistant",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router, prefix="/api")

# Serve static files with absolute path
import os
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Serve index.html for root
@app.get("/")
def root():
    """Serve the main dashboard."""
    return FileResponse(os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates", "dashboard.html"))


@app.get("/import")
def import_page():
    """Serve the import page."""
    return FileResponse("templates/import.html")


@app.get("/queue")
def queue_page():
    """Serve the queue page."""
    return FileResponse("templates/queue.html")


@app.get("/person/{prospect_id}")
def person_page(prospect_id: int):
    """Serve the person details page."""
    return FileResponse("templates/person_details.html")


@app.get("/history")
def history_page():
    """Serve the history page."""
    return FileResponse("templates/history.html")


@app.get("/settings")
def settings_page():
    """Serve the settings page."""
    return FileResponse("templates/settings.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=APP_HOST, port=APP_PORT)
