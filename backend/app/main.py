"""
Main FastAPI Application Entrypoint.
Lunar Ice Intelligence and Traverse Planning System v2.0
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.exceptions import LunarScienceException, lunar_exception_handler
from app.api.api_router import router

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Scientific Decision Support for Chandrayaan-2 Radar Analysis, Landing Selection, and Rover Traverse Planning."
)

# CORS Middleware allowing local frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from fastapi.staticfiles import StaticFiles
from pathlib import Path

# Exception handlers
app.add_exception_handler(LunarScienceException, lunar_exception_handler)

# Include API routes
app.include_router(router, prefix=settings.API_V1_STR)

# Serve Tile Pyramids for Leaflet GIS Map Viewer
tiles_dir = Path(__file__).resolve().parent.parent / "tiles"
tiles_dir.mkdir(parents=True, exist_ok=True)
app.mount("/tiles", StaticFiles(directory=str(tiles_dir)), name="tiles")


@app.get("/")
def root():
    return {
        "message": f"Welcome to {settings.PROJECT_NAME} v{settings.VERSION}",
        "documentation": "/docs",
        "api_v1": settings.API_V1_STR
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
