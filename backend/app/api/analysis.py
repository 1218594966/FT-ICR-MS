import math
import shutil
from pathlib import Path
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from app.models.database import get_db, Task
from app.schemas.task_schema import TaskCreate
from app.tasks.analysis_task import start_analysis
from app.config import settings

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


def _sanitize(obj):
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    return obj


@router.post("/start")
def start_analysis_endpoint(body: TaskCreate, file_path: str, filename: str, db: Session = Depends(get_db)):
    try:
        resolved_file = Path(file_path).resolve()
        upload_root = settings.UPLOAD_DIR.resolve()
        if upload_root != resolved_file and upload_root not in resolved_file.parents:
            raise ValueError
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid upload path")

    filename = Path(filename or "analysis").name
    ref_file = str(settings.REF_DIR / "Hawkes_neg.ref")

    params_dict = body.params.model_dump()
    atoms = params_dict.get("preliminary_search", {}).get("used_atoms", {})
    if atoms:
        params_dict["preliminary_search"]["used_atoms"] = {
            k: v for k, v in atoms.items() if v and v != [0, 0]
        }
    atoms_full = params_dict.get("full_search", {}).get("used_atoms", {})
    if atoms_full:
        params_dict["full_search"]["used_atoms"] = {
            k: v for k, v in atoms_full.items() if v and v != [0, 0]
        }

    task = Task(
        filename=filename,
        task_type="analysis",
        status="pending",
        params=params_dict,
        ref_file=ref_file,
        upload_dir=str(resolved_file),
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    start_analysis(task.id)

    return {
        "id": task.id,
        "filename": task.filename,
        "status": task.status,
        "current_step": task.current_step or "",
        "progress": task.progress or 0,
        "created_at": task.created_at.isoformat() if task.created_at else None,
    }


@router.get("/{task_id}")
def get_task(task_id: str, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {
        "id": task.id,
        "filename": task.filename,
        "task_type": task.task_type or "analysis",
        "status": task.status,
        "current_step": task.current_step or "",
        "progress": task.progress or 0,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "finished_at": task.finished_at.isoformat() if task.finished_at else None,
        "error_message": task.error_message,
        "params": task.params,
        "result": _sanitize(task.result),
        "csv_path": task.csv_path,
    }


@router.get("/{task_id}/status")
def get_task_status(task_id: str, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {
        "id": task.id,
        "status": task.status,
        "current_step": task.current_step,
        "progress": task.progress,
    }


@router.delete("/{task_id}")
def delete_task(task_id: str, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    candidate_dirs = [settings.UPLOAD_DIR / task_id]
    candidate_files = []
    if task.upload_dir:
        upload_path = Path(task.upload_dir)
        if upload_path.is_file():
            candidate_files.append(upload_path)
        elif upload_path.is_dir():
            candidate_dirs.append(upload_path)
        try:
            upload_root = settings.UPLOAD_DIR.resolve()
            resolved_upload = upload_path.resolve()
            relative = resolved_upload.relative_to(upload_root)
            if relative.parts:
                candidate_dirs.append(upload_root / relative.parts[0])
        except ValueError:
            pass
    if task.task_type == "dpr":
        candidate_dirs.append(settings.UPLOAD_DIR / "data_analysis" / task_id)

    for upload_file in candidate_files:
        if upload_file.exists() and upload_file.is_file():
            upload_file.unlink()

    for upload_dir in candidate_dirs:
        if upload_dir.exists() and upload_dir.is_dir():
            shutil.rmtree(upload_dir, ignore_errors=True)

    candidate_csvs = [settings.RESULT_DIR / f"{task_id}.csv"]
    if task.csv_path:
        candidate_csvs.append(Path(task.csv_path))

    for csv_path in candidate_csvs:
        if csv_path.exists() and csv_path.is_file():
            csv_path.unlink()

    db.delete(task)
    db.commit()
    return {"message": "Task deleted"}
