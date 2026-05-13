import os
import uuid
import zipfile
import shutil
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException
from app.config import settings

router = APIRouter(prefix="/api/upload", tags=["upload"])

CHUNK_SIZE = 1024 * 1024


def _safe_child(base: Path, relative_path: str) -> Path:
    clean = relative_path.replace("\\", "/").lstrip("/")
    dest = (base / clean).resolve()
    base_resolved = base.resolve()
    if base_resolved != dest and base_resolved not in dest.parents:
        raise HTTPException(status_code=400, detail="Invalid file path")
    return dest


def _extract_zip_safely(zip_path: Path, extract_dir: Path):
    with zipfile.ZipFile(zip_path, "r") as zf:
        for member in zf.infolist():
            dest = _safe_child(extract_dir, member.filename)
            if member.is_dir():
                dest.mkdir(parents=True, exist_ok=True)
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(member) as src, open(dest, "wb") as out:
                shutil.copyfileobj(src, out)


async def _save_upload_file(file: UploadFile, dest: Path) -> int:
    size = 0
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "wb") as out:
        while True:
            chunk = await file.read(CHUNK_SIZE)
            if not chunk:
                break
            out.write(chunk)
            size += len(chunk)
    return size


@router.post("/data")
async def upload_data_file(file: UploadFile = File(...)):
    task_id = str(uuid.uuid4())
    task_dir = settings.UPLOAD_DIR / task_id
    task_dir.mkdir(parents=True, exist_ok=True)

    filename = Path(file.filename or "upload").name
    dest = task_dir / filename

    size = await _save_upload_file(file, dest)

    file_path = str(dest)
    if filename.lower().endswith(".zip"):
        extract_dir = task_dir / "extracted"
        extract_dir.mkdir(exist_ok=True)
        try:
            _extract_zip_safely(dest, extract_dir)
            extracted = list(extract_dir.iterdir())
            d_dirs = [d for d in extracted if d.is_dir() and d.suffix.lower() == ".d"]
            if d_dirs:
                file_path = str(d_dirs[0])
            elif len(extracted) == 1 and extracted[0].is_dir():
                file_path = str(extracted[0])
            else:
                file_path = str(extract_dir)
        except zipfile.BadZipFile:
            raise HTTPException(status_code=400, detail="Invalid ZIP file")

    return {
        "task_id": task_id,
        "filename": filename,
        "file_path": file_path,
        "size": size,
    }


@router.post("/folder")
async def upload_folder(files: list[UploadFile] = File(...)):
    task_id = str(uuid.uuid4())
    task_dir = settings.UPLOAD_DIR / task_id
    task_dir.mkdir(parents=True, exist_ok=True)

    d_root_name = None
    for file in files:
        rel_path = file.filename or ""
        parts = rel_path.replace("\\", "/").split("/")
        if len(parts) > 1:
            dest = _safe_child(task_dir, rel_path)
            dest.parent.mkdir(parents=True, exist_ok=True)
            if d_root_name is None and parts[0].endswith(".d"):
                d_root_name = parts[0]
        else:
            dest = _safe_child(task_dir, rel_path)
        await _save_upload_file(file, dest)

    if d_root_name:
        file_path = str(task_dir / d_root_name)
    else:
        file_path = str(task_dir)

    return {
        "task_id": task_id,
        "filename": d_root_name or "folder_upload",
        "file_path": file_path,
        "file_count": len(files),
    }
