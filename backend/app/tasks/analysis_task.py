import os
import sys
import shutil
import threading
import traceback
from pathlib import Path
from datetime import datetime

BACKEND_DIR = str(Path(__file__).resolve().parent.parent.parent)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.config import settings
from app.models.database import SessionLocal, Task
from app.core.pipeline import AnalysisPipeline, extract_upload

_lock = threading.Lock()

_STEP_KEYS = {
    1: "peak_detection",
    2: "kendrick_filter",
    3: "preliminary_search",
    4: "calibration",
    5: "full_search",
    6: "indices_calc",
    7: "nitrogen_rule",
    8: "classification",
    9: "weighted_avg",
}


def _update_task(task_id: str, **kwargs):
    with _lock:
        db = SessionLocal()
        try:
            task = db.query(Task).filter(Task.id == task_id).first()
            if task:
                for k, v in kwargs.items():
                    setattr(task, k, v)
                db.commit()
        finally:
            db.close()


def _run_analysis(task_id: str):
    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            return

        _update_task(task_id, status="running", started_at=datetime.utcnow())

        params = task.params or {}
        file_path = task.upload_dir

        if not os.path.isdir(file_path):
            extract_dir = os.path.join(settings.UPLOAD_DIR, task_id, "extracted")
            os.makedirs(extract_dir, exist_ok=True)
            file_path = extract_upload(file_path, extract_dir)

        def progress_cb(step: int, step_name: str, pct: int):
            overall = ((step - 1) / 9 * 100) + (pct / 9)
            _update_task(
                task_id,
                current_step=_STEP_KEYS.get(step, step_name),
                progress=round(overall, 1),
            )

        pipeline = AnalysisPipeline(
            file_path=file_path,
            params=params,
            ref_file=task.ref_file or str(settings.REF_DIR / "Hawkes_neg.ref"),
            db_url=f"sqlite:///{(settings.LOCAL_DB_DIR / 'molformulas.sqlite').as_posix()}",
        )
        result = pipeline.run(progress_cb=progress_cb)

        csv_path = result.get("csv_path")
        if csv_path and os.path.exists(csv_path):
            dest = os.path.join(settings.RESULT_DIR, f"{task_id}.csv")
            shutil.copy2(csv_path, dest)
            csv_path = dest

        _update_task(
            task_id,
            status="success",
            finished_at=datetime.utcnow(),
            result=result,
            csv_path=csv_path,
            progress=100.0,
            current_step="completed",
        )

    except Exception as e:
        tb = traceback.format_exc()
        _update_task(
            task_id,
            status="failed",
            finished_at=datetime.utcnow(),
            error_message=f"{str(e)}\n{tb}",
        )
    finally:
        db.close()


def start_analysis(task_id: str):
    t = threading.Thread(target=_run_analysis, args=(task_id,), daemon=True)
    t.start()
    return t
