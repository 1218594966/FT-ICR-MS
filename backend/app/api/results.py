import math
import os
import re
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.models.database import get_db, Task
from app.config import settings

router = APIRouter(prefix="/api/results", tags=["results"])


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


def _clean_list(lst):
    return [x if isinstance(x, (int, float)) and math.isfinite(x) else 0 for x in lst]


_ELEM_CATEGORY_MAP = {
    frozenset({'C','H','O'}): 'CHO',
    frozenset({'C','H','O','N'}): 'CHON',
    frozenset({'C','H','O','S'}): 'CHOS',
    frozenset({'C','H','O','N','S'}): 'CHONS',
    frozenset({'C','H','O','P'}): 'CHOP',
    frozenset({'C','H','O','N','P'}): 'CHONP',
    frozenset({'C','H','O','P','S'}): 'CHOPS',
    frozenset({'C','H','O','N','P','S'}): 'CHONPS',
    frozenset({'C','H','O','Cl'}): 'CHOCl',
    frozenset({'C','H','O','N','Cl'}): 'CHONCl',
    frozenset({'C','H','O','S','Cl'}): 'CHOSCl',
    frozenset({'C','H','O','N','S','Cl'}): 'CHONSCl',
}


def _normalize_elem_category(category: str) -> str:
    if not isinstance(category, str) or not category:
        return "Other"
    if category in set(_ELEM_CATEGORY_MAP.values()) | {"Other"}:
        return category
    tokens = re.findall(r"Cl|[A-Z][a-z]?", category)
    if not tokens and set(category).issubset(set("CHONPS")):
        tokens = list(category)
    elems = set(tokens)
    if "C" not in elems or "H" not in elems or "O" not in elems:
        return "Other"
    return _ELEM_CATEGORY_MAP.get(frozenset(elems), "Other")


@router.get("/{task_id}/data")
def get_result_data(task_id: str, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status != "success":
        raise HTTPException(status_code=400, detail=f"Task status: {task.status}")
    return _sanitize(task.result)


@router.get("/{task_id}/export")
def export_csv(task_id: str, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if not task.csv_path or not os.path.exists(task.csv_path):
        raise HTTPException(status_code=404, detail="CSV file not found")
    
    # Generate appropriate filename based on task type
    if task.task_type == 'dpr':
        filename = f"{task.filename}_DPR_result.csv"
    else:
        filename = f"{task.filename}_result.csv"
    
    return FileResponse(
        path=task.csv_path,
        filename=filename,
        media_type="text/csv",
    )


@router.get("/{task_id}/chart/{chart_type}")
def get_chart_data(task_id: str, chart_type: str, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status != "success" or not task.result:
        raise HTTPException(status_code=400, detail="No results available")

    result = task.result
    steps = result.get("steps", {})

    if chart_type == "spectrum":
        d = steps.get("peak_detection", {}).get("data", {})
        return {"mz": _clean_list(d.get("mz", [])), "abundance": _clean_list(d.get("abundance", []))}

    elif chart_type in {"preliminary", "error"}:
        d = steps.get("preliminary_search", {}).get("data", {})
        return {"mz": _clean_list(d.get("mz", [])), "ppm_error": _clean_list(d.get("ppm_error", [])), "formulas": d.get("formulas", [])}

    elif chart_type == "vankrevelen":
        d = steps.get("full_search", {}).get("data", {})
        return {
            "oc": _clean_list(d.get("oc", [])),
            "hc": _clean_list(d.get("hc", [])),
            "elem_category": [_normalize_elem_category(c) for c in d.get("elem_category", [])],
        }

    elif chart_type == "classification":
        d = steps.get("classification", {}).get("data", {})
        return d.get("type_counts", {})

    elif chart_type == "weighted":
        d = steps.get("weighted_avg", {}).get("data", {})
        return _sanitize(d.get("weighted_averages", {}))

    else:
        raise HTTPException(status_code=400, detail=f"Unknown chart type: {chart_type}")
