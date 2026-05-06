import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.config import settings, get_default_params
from app.models.database import init_db
from app.api import upload, analysis, results, history, export, data_analysis, ml_analysis, source_database, batch, pmd_analysis

app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload.router)
app.include_router(analysis.router)
app.include_router(results.router)
app.include_router(history.router)
app.include_router(export.router)
app.include_router(data_analysis.router)
app.include_router(ml_analysis.router)
app.include_router(source_database.router)
app.include_router(batch.router)
app.include_router(pmd_analysis.router)

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"


@app.on_event("startup")
def startup():
    init_db()


@app.get("/api/health")
def health():
    return {"status": "ok", "version": settings.APP_VERSION}


@app.get("/api/config/defaults")
def get_defaults():
    return get_default_params()


@app.get("/api/config/ref-files")
def list_ref_files():
    ref_dir = settings.REF_DIR
    files = [f.name for f in ref_dir.iterdir() if f.suffix.lower() == ".ref"]
    return {"files": files}


if FRONTEND_DIR.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        file_path = FRONTEND_DIR / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(FRONTEND_DIR / "index.html")
