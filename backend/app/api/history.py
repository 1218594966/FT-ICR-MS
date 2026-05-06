import math
import re
import shutil
import time
import uuid
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, Query, HTTPException, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.config import get_default_params, settings
from app.core.pipeline import (
    PipelineContext,
    step6_indices_calc,
    step7_nitrogen_rule,
    step8_classification,
    step9_weighted_avg,
)
from app.models.database import get_db, Task

router = APIRouter(prefix="/api/history", tags=["history"])


class RenameRequest(BaseModel):
    filename: str


DERIVED_COLUMNS = [
    "N/C", "S/C", "P/C", "AImod", "NOSC",
    "DBE-O", "DBE/C", "DBE/H", "DBE/O", "is_CRAM",
]
REQUIRED_IMPORT_COLUMNS = ["Molecular Formula", "C", "H", "O", "DBE", "Peak Height", "O/C", "H/C"]
NUMERIC_COLUMNS = [
    "C", "H", "O", "N", "P", "S", "Cl", "F", "13C", "18O", "33S", "34S",
    "DBE", "Peak Height", "Peak Area", "O/C", "H/C", "m/z", "Calibrated m/z",
    "Calculated m/z", "m/z Error (ppm)", "Resolving Power", "S/N",
]
OPTIONAL_ELEMENT_COLUMNS = ["N", "P", "S", "Cl", "F"]
VK_CATEGORY_ELEMENTS = ["N", "S", "P", "Cl"]
ELEM_CAT_MAP = {
    frozenset({"C", "H", "O"}): "CHO",
    frozenset({"C", "H", "O", "N"}): "CHON",
    frozenset({"C", "H", "O", "S"}): "CHOS",
    frozenset({"C", "H", "O", "N", "S"}): "CHONS",
    frozenset({"C", "H", "O", "P"}): "CHOP",
    frozenset({"C", "H", "O", "N", "P"}): "CHONP",
    frozenset({"C", "H", "O", "P", "S"}): "CHOPS",
    frozenset({"C", "H", "O", "N", "P", "S"}): "CHONPS",
    frozenset({"C", "H", "O", "Cl"}): "CHOCl",
    frozenset({"C", "H", "O", "N", "Cl"}): "CHONCl",
    frozenset({"C", "H", "O", "S", "Cl"}): "CHOSCl",
    frozenset({"C", "H", "O", "N", "S", "Cl"}): "CHONSCl",
}


def _read_csv_auto(path: Path) -> pd.DataFrame:
    last_error = None
    for enc in ("utf-8-sig", "utf-8", "gb18030", "gbk", "latin1"):
        try:
            return pd.read_csv(path, encoding=enc)
        except UnicodeDecodeError as exc:
            last_error = exc
    raise ValueError(f"Failed to read CSV: {last_error}")


def _json_safe(obj):
    if obj is None:
        return None
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating, float)):
        value = float(obj)
        return value if math.isfinite(value) else None
    if isinstance(obj, np.ndarray):
        return [_json_safe(v) for v in obj.tolist()]
    if isinstance(obj, dict):
        return {str(k): _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    return obj


def _clean_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip().lstrip("\ufeff") for c in df.columns]
    return df


def _numeric_list(df: pd.DataFrame, column: str) -> list:
    if column not in df.columns:
        return []
    values = pd.to_numeric(df[column], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0)
    return values.astype(float).tolist()


def _formula_list(df: pd.DataFrame) -> list:
    if "Molecular Formula" not in df.columns:
        return []
    return df["Molecular Formula"].fillna("").astype(str).tolist()


def _parse_formula_counts(formula: str) -> dict:
    if not isinstance(formula, str):
        return {}
    counts = {}
    for elem, count in re.findall(r"([A-Z][a-z]?)(\d*)", formula.replace(" ", "")):
        counts[elem] = counts.get(elem, 0) + (int(count) if count else 1)
    return counts


def _fill_missing_optional_elements(df: pd.DataFrame) -> pd.DataFrame:
    missing = [elem for elem in OPTIONAL_ELEMENT_COLUMNS if elem not in df.columns]
    if not missing or "Molecular Formula" not in df.columns:
        for elem in missing:
            df[elem] = 0
        return df

    parsed = df["Molecular Formula"].fillna("").astype(str).map(_parse_formula_counts)
    for elem in missing:
        df[elem] = parsed.map(lambda counts: counts.get(elem, 0))
    return df


def _element_category(row, category_elements: list[str] | None = None) -> str:
    selected = set(category_elements or VK_CATEGORY_ELEMENTS)
    elems = {"C", "H", "O"}
    for elem in selected:
        value = pd.to_numeric(row.get(elem, 0), errors="coerce")
        if pd.notna(value) and value > 0:
            elems.add(elem)
    return ELEM_CAT_MAP.get(frozenset(elems), "Other")


def _build_import_result(
    df: pd.DataFrame,
    steps: dict,
    total_time: float,
    csv_path: str,
    category_elements: list[str] | None = None,
) -> dict:
    assigned = df[df["Molecular Formula"].notna() & (df["Molecular Formula"].astype(str).str.strip() != "")].copy()
    total = len(df)
    assigned_count = len(assigned)
    imported_steps = {
        "peak_detection": {
            "status": "success",
            "data": {
                "total_peaks": total,
                "mz": _numeric_list(df, "m/z"),
                "abundance": _numeric_list(df, "Peak Height"),
            },
            "time": 0,
        },
        "preliminary_search": {
            "status": "success",
            "data": {
                "status": "imported",
                "mz": _numeric_list(df, "m/z"),
                "ppm_error": _numeric_list(df, "m/z Error (ppm)"),
                "formulas": _formula_list(df),
            },
            "time": 0,
        },
        "full_search": {
            "status": "success",
            "data": {
                "total_peaks": total,
                "assigned_peaks": assigned_count,
                "unassigned_peaks": total - assigned_count,
                "assignment_rate": round(assigned_count / total * 100, 2) if total else 0,
                "mz": _numeric_list(df, "m/z"),
                "ppm_error": _numeric_list(df, "m/z Error (ppm)"),
                "formulas": _formula_list(df),
                "oc": _numeric_list(assigned, "O/C"),
                "hc": _numeric_list(assigned, "H/C"),
                "elem_category": [_element_category(row, category_elements) for _, row in assigned.iterrows()],
                "category_elements": category_elements or VK_CATEGORY_ELEMENTS,
            },
            "time": 0,
        },
    }
    imported_steps.update(steps)
    return {
        "steps": imported_steps,
        "csv_path": csv_path,
        "total_time": round(total_time, 2),
        "error": None,
        "imported": True,
    }


def _complete_regular_analysis_csv(df: pd.DataFrame) -> tuple[pd.DataFrame, dict, float]:
    df = _clean_columns(df)
    missing = [col for col in REQUIRED_IMPORT_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError("CSV 缺少常规分析必要列: " + ", ".join(missing))

    original_rows = len(df)
    for col in NUMERIC_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df = _fill_missing_optional_elements(df)
    existing_derived = [col for col in DERIVED_COLUMNS if col in df.columns]
    if existing_derived:
        df = df.drop(columns=existing_derived)

    full_search_params = get_default_params().get("full_search", {})
    oc_min = full_search_params.get("min_oc", 0.0)
    oc_max = full_search_params.get("max_oc", 1.2)
    hc_min = full_search_params.get("min_hc", 0.3)
    hc_max = full_search_params.get("max_hc", 2.25)
    df = df[
        df["Molecular Formula"].notna()
        & (df["Molecular Formula"].astype(str).str.strip() != "")
        & df["O/C"].between(oc_min, oc_max, inclusive="both")
        & df["H/C"].between(hc_min, hc_max, inclusive="both")
    ].copy()
    range_filtered_rows = len(df)

    ctx = PipelineContext(mso_df=df)
    steps = {}
    total_time = 0.0
    for step_name, step_fn in (
        ("indices_calc", step6_indices_calc),
        ("nitrogen_rule", step7_nitrogen_rule),
        ("classification", step8_classification),
        ("weighted_avg", step9_weighted_avg),
    ):
        t0 = time.time()
        data = step_fn(ctx)
        elapsed = round(time.time() - t0, 2)
        total_time += elapsed
        steps[step_name] = {"status": "success", "data": _json_safe(data), "time": elapsed}

    if ctx.mso_df is None or ctx.mso_df.empty:
        raise ValueError("CSV 处理后没有可用分子，请检查 Molecular Formula、DBE、C/H/O、O/C、H/C 等列。")
    steps["import_filter"] = {
        "status": "success",
        "data": {
            "original_rows": original_rows,
            "after_formula_oc_hc_filter": range_filtered_rows,
            "oc_range": [oc_min, oc_max],
            "hc_range": [hc_min, hc_max],
        },
        "time": 0,
    }
    return ctx.mso_df, steps, total_time


@router.get("")
def list_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str = Query(None),
    keyword: str = Query(None),
    task_type: str = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(Task)
    if status:
        query = query.filter(Task.status == status)
    if keyword:
        query = query.filter(Task.filename.contains(keyword))
    if task_type:
        query = query.filter(Task.task_type == task_type)

    total = query.count()
    tasks = (
        query.order_by(desc(Task.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "tasks": [
            {
                "id": t.id,
                "filename": t.filename,
                "task_type": t.task_type or "analysis",
                "status": t.status,
                "current_step": t.current_step or "",
                "progress": t.progress or 0,
                "created_at": t.created_at.isoformat() if t.created_at else None,
                "started_at": t.started_at.isoformat() if t.started_at else None,
                "finished_at": t.finished_at.isoformat() if t.finished_at else None,
                "error_message": t.error_message,
            }
            for t in tasks
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.put("/{task_id}/rename")
def rename_task(task_id: str, req: RenameRequest, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    task.filename = req.filename
    db.commit()
    return {"id": task.id, "filename": task.filename}


@router.post("/import-analysis-csv")
async def import_regular_analysis_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="请上传 CSV 文件")

    task_id = str(uuid.uuid4())
    filename = Path(file.filename).name
    task_dir = settings.UPLOAD_DIR / "imported_analysis" / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    uploaded_path = task_dir / filename

    try:
        with uploaded_path.open("wb") as out:
            shutil.copyfileobj(file.file, out)

        raw_df = _read_csv_auto(uploaded_path)
        completed_df, steps, total_time = _complete_regular_analysis_csv(raw_df)

        result_path = settings.RESULT_DIR / f"{task_id}.csv"
        completed_df.to_csv(result_path, index=False, encoding="utf-8-sig")

        result = _build_import_result(completed_df, steps, total_time, str(result_path))
        now = datetime.utcnow()
        task = Task(
            id=task_id,
            filename=filename,
            task_type="analysis",
            status="success",
            current_step="completed",
            progress=100.0,
            params={"imported_from_csv": True},
            upload_dir=str(task_dir),
            created_at=now,
            started_at=now,
            finished_at=now,
            result=_json_safe(result),
            csv_path=str(result_path),
        )
        db.add(task)
        db.commit()
        db.refresh(task)

        return {
            "id": task.id,
            "filename": task.filename,
            "status": task.status,
            "rows": len(completed_df),
            "csv_path": task.csv_path,
        }
    except ValueError as exc:
        shutil.rmtree(task_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        shutil.rmtree(task_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail=f"导入常规分析 CSV 失败: {exc}")
