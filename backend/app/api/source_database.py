import base64
import io
import re
from urllib.parse import quote
from datetime import datetime
from typing import List, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from scipy.stats import chi2_contingency
from sqlalchemy.orm import Session

from app.models.database import MolecularDatabase, get_db
from app.core.fonts import apply_font_to_figure, configure_matplotlib_fonts

router = APIRouter(prefix="/api/source-db", tags=["source-database"])


def _read_csv_auto(path_or_buffer):
    last_error = None
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "gbk", "latin1"):
        try:
            return pd.read_csv(path_or_buffer, encoding=encoding)
        except UnicodeDecodeError as exc:
            last_error = exc
            if hasattr(path_or_buffer, "seek"):
                path_or_buffer.seek(0)
    if last_error:
        raise last_error
    return pd.read_csv(path_or_buffer)


def _normalized_columns(df):
    return {str(col).strip().lower().replace("_", " "): col for col in df.columns}


def _find_formula_col(df):
    normalized = _normalized_columns(df)
    for candidate in ("Molecular Formula", "MolForm", "Formula", "formula"):
        key = candidate.strip().lower().replace("_", " ")
        if key in normalized:
            return normalized[key]
    return None


def _find_intensity_col(df):
    normalized = _normalized_columns(df)
    for candidate in ("Peak Height", "PeakHeight", "Peak_Height", "Intensity", "intensity", "峰高", "强度"):
        key = candidate.strip().lower().replace("_", " ")
        if key in normalized:
            return normalized[key]
    return None


async def _read_molecule_map(file: UploadFile):
    try:
        await file.seek(0)
        df = _read_csv_auto(file.file)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to read {file.filename}: {exc}")

    formula_col = _find_formula_col(df)
    if not formula_col:
        raise HTTPException(status_code=400, detail=f"{file.filename} must contain 'Molecular Formula' or 'MolForm'")

    intensity_col = _find_intensity_col(df)
    clean = pd.DataFrame({"formula": df[formula_col].dropna().astype(str).str.strip()})
    clean = clean[clean["formula"] != ""]
    if intensity_col:
        clean["intensity"] = pd.to_numeric(df.loc[clean.index, intensity_col], errors="coerce").fillna(0).clip(lower=0)
    else:
        clean["intensity"] = 1.0

    grouped = clean.groupby("formula", as_index=True)["intensity"].sum()
    return {str(formula): float(value) for formula, value in grouped.items()}


async def _read_formula_set(file: UploadFile):
    return set((await _read_molecule_map(file)).keys())


def _safe_chi2(table, label):
    try:
        chi2, p_value, dof, expected = chi2_contingency(table)
        return {"method": f"Chi-squared Test ({label})", "chi2": float(chi2), "p_value": float(p_value), "dof": int(dof)}
    except ValueError:
        return {"method": f"N/A ({label})", "chi2": None, "p_value": None, "dof": None}


def _rate(part, total):
    return round(part / total * 100, 4) if total else 0


def _sum_intensity(weights, formulas=None):
    keys = weights.keys() if formulas is None else formulas
    return float(sum(float(weights.get(k, 0) or 0) for k in keys))


def _fig_to_base64(fig):
    buf = io.BytesIO()
    apply_font_to_figure(fig)
    fig.savefig(buf, format="png", dpi=180, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def _fig_to_pdf_base64(fig):
    buf = io.BytesIO()
    apply_font_to_figure(fig)
    fig.savefig(buf, format="pdf", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def _configure_plot_fonts():
    configure_matplotlib_fonts("Times New Roman", pdf_fonttype=42)


def _heatmap(data, row_labels, title, p_value=None, output_format="png"):
    _configure_plot_fonts()
    fig, ax = plt.subplots(figsize=(9, 6))
    arr = np.array(data)
    row_sums = arr.sum(axis=1, keepdims=True)
    row_sums_safe = np.where(row_sums == 0, 1, row_sums)
    percentages = arr / row_sums_safe * 100
    annot = np.empty_like(arr, dtype=object)
    for i in range(arr.shape[0]):
        for j in range(arr.shape[1]):
            annot[i, j] = f"{arr[i, j]}\n({percentages[i, j]:.1f}%)" if row_sums[i] > 0 else f"{arr[i, j]}\n(N/A)"

    sns.heatmap(
        arr,
        annot=annot,
        fmt="",
        cmap="Blues",
        linewidths=1.5,
        linecolor="white",
        xticklabels=["Present in\nSource DB", "Absent from\nSource DB"],
        yticklabels=row_labels,
        cbar_kws={"label": "Number of Molecules"},
        ax=ax,
    )
    suffix = ""
    if p_value is not None:
        suffix = f"\nChi-squared p={p_value:.5f}" + (" (Significant)" if p_value < 0.05 else " (n.s.)")
    ax.set_title(title + suffix, fontsize=14, pad=16)
    ax.set_xlabel("Presence in merged source database")
    ax.set_ylabel("Molecular fate")
    ax.tick_params(axis="y", labelrotation=0)
    plt.tight_layout()
    if output_format == "pdf":
        return _fig_to_pdf_base64(fig)
    return _fig_to_base64(fig)


def _element_class(formula: str):
    elems = set(re.findall(r"Cl|[A-Z][a-z]?", formula or ""))
    category_map = {
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
    return category_map.get(frozenset(elems), "Other")


def _class_rows(groups):
    fixed_classes = [
        "CHO", "CHON", "CHOS", "CHONS", "CHOP", "CHONP",
        "CHOPS", "CHONPS", "CHOCl", "CHONCl", "CHOSCl", "CHONSCl",
    ]
    observed = {_element_class(formula) for formulas in groups.values() for formula in formulas}
    classes = fixed_classes + (["Other"] if "Other" in observed else [])
    rows = []
    for cls in classes:
        row = {"class": cls}
        for name, formulas in groups.items():
            row[name] = sum(1 for formula in formulas if _element_class(formula) == cls)
        rows.append(row)
    return rows


def _compare_bar_plot(overlap, query_only, db_only):
    _configure_plot_fonts()
    fig, ax = plt.subplots(figsize=(7, 4.2))
    labels = ["Overlap", "Sample only", "Database only"]
    values = [len(overlap), len(query_only), len(db_only)]
    colors = ["#2563eb", "#f97316", "#64748b"]
    ax.bar(labels, values, color=colors)
    ax.set_ylabel("Number of Molecules")
    ax.set_title("Sample vs. Molecular Database")
    for i, v in enumerate(values):
        ax.text(i, v, str(v), ha="center", va="bottom", fontsize=11)
    plt.tight_layout()
    return _fig_to_base64(fig)


def _csv_base64(formulas, column_name="Molecular Formula"):
    buf = io.StringIO()
    pd.DataFrame({column_name: sorted(formulas)}).to_csv(buf, index=False)
    return base64.b64encode(buf.getvalue().encode("utf-8-sig")).decode("utf-8")


def _csv_with_intensity_base64(formulas, intensities):
    buf = io.StringIO()
    pd.DataFrame({
        "Molecular Formula": sorted(formulas),
        "Peak Height": [float(intensities[f]) if f in intensities else "" for f in sorted(formulas)],
    }).to_csv(buf, index=False)
    return base64.b64encode(buf.getvalue().encode("utf-8-sig")).decode("utf-8")


def _database_intensities(item: MolecularDatabase):
    totals = {}
    for source in item.files or []:
        intensities = source.get("intensities") or {}
        for formula, value in intensities.items():
            totals[formula] = float(totals.get(formula, 0) or 0) + float(value or 0)
    return totals


def _db_summary(item: MolecularDatabase):
    return {
        "id": item.id,
        "name": item.name,
        "description": item.description or "",
        "formula_count": item.formula_count or 0,
        "file_count": item.file_count or 0,
        "files": [
            {
                "filename": f.get("filename"),
                "formula_count": f.get("formula_count", 0),
                "added_at": f.get("added_at"),
            }
            for f in (item.files or [])
        ],
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


@router.get("/databases")
def list_databases(db: Session = Depends(get_db)):
    items = db.query(MolecularDatabase).order_by(MolecularDatabase.updated_at.desc()).all()
    return {"databases": [_db_summary(item) for item in items]}


@router.post("/databases")
async def create_or_append_database(
    files: List[UploadFile] = File(...),
    database_id: Optional[str] = Form(None),
    name: str = Form("Molecular Database"),
    description: str = Form(""),
    db: Session = Depends(get_db),
):
    if not files:
        raise HTTPException(status_code=400, detail="At least one CSV file is required")

    target = None
    if database_id:
        target = db.query(MolecularDatabase).filter(MolecularDatabase.id == database_id).first()
        if not target:
            raise HTTPException(status_code=404, detail="Database not found")
    else:
        clean_name = (name or "").strip()
        if not clean_name:
            raise HTTPException(status_code=400, detail="Database name is required")
        target = db.query(MolecularDatabase).filter(MolecularDatabase.name == clean_name).first()
        if not target:
            target = MolecularDatabase(name=clean_name, description=description or "", formulas=[], files=[])
            db.add(target)

    current_formulas = set(target.formulas or [])
    file_records = list(target.files or [])
    current_intensities = _database_intensities(target)
    uploaded = []

    for file in files:
        molecule_map = await _read_molecule_map(file)
        formulas = set(molecule_map)
        before = len(current_formulas)
        current_formulas |= formulas
        for formula, value in molecule_map.items():
            current_intensities[formula] = float(current_intensities.get(formula, 0) or 0) + float(value or 0)
        uploaded.append({
            "filename": file.filename,
            "formula_count": len(formulas),
            "new_unique_count": len(current_formulas) - before,
            "total_intensity": round(_sum_intensity(molecule_map), 6),
        })
        file_records.append({
            "filename": file.filename,
            "formula_count": len(formulas),
            "formulas": sorted(formulas),
            "intensities": molecule_map,
            "total_intensity": round(_sum_intensity(molecule_map), 6),
            "added_at": datetime.utcnow().isoformat(),
        })

    target.formulas = sorted(current_formulas)
    target.files = file_records
    target.formula_count = len(current_formulas)
    target.file_count = len(file_records)
    if description:
        target.description = description
    target.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(target)

    return {
        "database": _db_summary(target),
        "uploaded": uploaded,
        "database_csv_base64": _csv_with_intensity_base64(current_formulas, current_intensities),
    }


@router.get("/databases/{database_id}/download")
def download_database(database_id: str, db: Session = Depends(get_db)):
    item = db.query(MolecularDatabase).filter(MolecularDatabase.id == database_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Database not found")
    buf = io.BytesIO()
    formulas = sorted(item.formulas or [])
    intensities = _database_intensities(item)
    pd.DataFrame({
        "Molecular Formula": formulas,
        "Peak Height": [float(intensities[f]) if f in intensities else "" for f in formulas],
    }).to_csv(buf, index=False, encoding="utf-8-sig")
    buf.seek(0)
    safe_name = re.sub(r'[\\/:*?"<>|]+', "_", item.name) or "molecular_database"
    ascii_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", safe_name) or "molecular_database"
    quoted_name = quote(f"{safe_name}.csv")
    return StreamingResponse(
        buf,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=\"{ascii_name}.csv\"; filename*=UTF-8''{quoted_name}"},
    )


@router.delete("/databases/{database_id}")
def delete_database(database_id: str, db: Session = Depends(get_db)):
    item = db.query(MolecularDatabase).filter(MolecularDatabase.id == database_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Database not found")
    db.delete(item)
    db.commit()
    return {"id": database_id, "deleted": True}


@router.post("/compare")
async def compare_with_database(
    query_file: UploadFile = File(...),
    database_id: str = Form(...),
    db: Session = Depends(get_db),
):
    item = db.query(MolecularDatabase).filter(MolecularDatabase.id == database_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Database not found")

    database_formulas = set(item.formulas or [])
    database_intensities = _database_intensities(item)
    query_intensities = await _read_molecule_map(query_file)
    query_formulas = set(query_intensities)
    overlap = query_formulas & database_formulas
    query_only = query_formulas - database_formulas
    database_only = database_formulas - query_formulas

    source_file_rows = []
    for source in item.files or []:
        source_formulas = set(source.get("formulas") or [])
        matched = query_formulas & source_formulas
        source_file_rows.append({
            "filename": source.get("filename"),
            "formula_count": len(source_formulas),
            "overlap": len(matched),
            "sample_coverage": _rate(len(matched), len(query_formulas)),
            "source_coverage": _rate(len(matched), len(source_formulas)),
        })
    source_file_rows.sort(key=lambda row: (row["sample_coverage"], row["overlap"]), reverse=True)

    return {
        "database": _db_summary(item),
        "query_filename": query_file.filename,
        "summary": {
            "query_count": len(query_formulas),
            "database_count": len(database_formulas),
            "overlap_count": len(overlap),
            "query_only_count": len(query_only),
            "database_only_count": len(database_only),
            "query_overlap_rate": _rate(len(overlap), len(query_formulas)),
            "database_coverage_rate": _rate(len(overlap), len(database_formulas)),
        },
        "source_file_similarity": source_file_rows,
        "element_class_distribution": _class_rows({
            "overlap": overlap,
            "sample_only": query_only,
            "database_only": database_only,
        }),
        "plots": {
            "comparison": _compare_bar_plot(overlap, query_only, database_only),
        },
        "downloads": {
            "overlap_csv_base64": _csv_with_intensity_base64(overlap, query_intensities),
            "sample_only_csv_base64": _csv_with_intensity_base64(query_only, query_intensities),
            "database_only_csv_base64": _csv_with_intensity_base64(database_only, database_intensities),
        },
        "suggestions": [
            "如果样品与某个来源数据库的样品覆盖率明显高，建议继续查看命中分子的元素类别分布，而不是只看总数量。",
            "如果存在多个来源数据库，可以对同一个样品批量比较，并用命中率排序判断样品更接近哪类来源。",
            "建议把 overlap、sample only、database only 三类分子分别导出，再进入机器学习或 VK/DBE/NOSC 图中比较类别差异。",
        ],
    }


@router.post("/compare-dpr")
async def compare_dpr_with_database(
    upstream_file: UploadFile = File(...),
    downstream_file: UploadFile = File(...),
    database_id: str = Form(...),
    remove_core: bool = Form(True),
    db: Session = Depends(get_db),
):
    item = db.query(MolecularDatabase).filter(MolecularDatabase.id == database_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Database not found")

    upstream = await _read_formula_set(upstream_file)
    downstream = await _read_formula_set(downstream_file)
    source_db = set(item.formulas or [])

    original_counts = {
        "upstream": len(upstream),
        "downstream": len(downstream),
        "source_database": len(source_db),
    }

    source_file_sets = [set(source.get("formulas") or []) for source in (item.files or []) if source.get("formulas")]
    source_common = set.intersection(*source_file_sets) if len(source_file_sets) >= 2 else set()
    core = (upstream & downstream & source_common) if remove_core and source_common else set()
    if core:
        upstream -= core
        downstream -= core
        source_db -= core

    disappearance = upstream - downstream
    product = downstream - upstream
    resistant = upstream & downstream

    d_in = len(disappearance & source_db)
    d_out = len(disappearance - source_db)
    p_in = len(product & source_db)
    p_out = len(product - source_db)
    r_in = len(resistant & source_db)
    r_out = len(resistant - source_db)

    table_3x2 = [[d_in, d_out], [p_in, p_out], [r_in, r_out]]
    table_pvsd = [[p_in, p_out], [d_in, d_out]]
    table_dvsr = [[d_in, d_out], [r_in, r_out]]

    test_3x2 = _safe_chi2(table_3x2, "3x2")
    test_pvsd = _safe_chi2(table_pvsd, "P vs D")
    test_dvsr = _safe_chi2(table_dvsr, "D vs R")

    return {
        "database": _db_summary(item),
        "upstream_filename": upstream_file.filename,
        "downstream_filename": downstream_file.filename,
        "original_counts": original_counts,
        "core_removed": len(core),
        "post_counts": {
            "upstream": len(upstream),
            "downstream": len(downstream),
            "source_database": len(source_db),
        },
        "fate_counts": {
            "D": len(disappearance),
            "P": len(product),
            "R": len(resistant),
        },
        "presence": {
            "D": {"in_source": d_in, "not_in_source": d_out, "presence_rate": _rate(d_in, d_in + d_out)},
            "P": {"in_source": p_in, "not_in_source": p_out, "presence_rate": _rate(p_in, p_in + p_out)},
            "R": {"in_source": r_in, "not_in_source": r_out, "presence_rate": _rate(r_in, r_in + r_out)},
        },
        "tests": {
            "overall_3x2": test_3x2,
            "p_vs_d": test_pvsd,
            "d_vs_r": test_dvsr,
        },
        "plots": {
            "overall_3x2": _heatmap(
                table_3x2,
                ["MDecay (D)\nUpstream only", "Mpdct (P)\nDownstream only", "MBkgd (R)\nBoth"],
                "Molecular Fate vs. Source Database",
                test_3x2["p_value"],
            ),
            "d_vs_r": _heatmap(table_dvsr, ["MDecay (D)", "MBkgd (R)"], "Disappeared (D) vs. Resistant (R)", test_dvsr["p_value"]),
            "p_vs_d": _heatmap(table_pvsd, ["Mpdct (P)", "MDecay (D)"], "Produced (P) vs. Disappeared (D)", test_pvsd["p_value"]),
        },
        "plot_pdfs": {
            "overall_3x2": _heatmap(
                table_3x2,
                ["MDecay (D)\nUpstream only", "Mpdct (P)\nDownstream only", "MBkgd (R)\nBoth"],
                "Molecular Fate vs. Source Database",
                test_3x2["p_value"],
                output_format="pdf",
            ),
            "d_vs_r": _heatmap(
                table_dvsr,
                ["MDecay (D)", "MBkgd (R)"],
                "Disappeared (D) vs. Resistant (R)",
                test_dvsr["p_value"],
                output_format="pdf",
            ),
            "p_vs_d": _heatmap(
                table_pvsd,
                ["Mpdct (P)", "MDecay (D)"],
                "Produced (P) vs. Disappeared (D)",
                test_pvsd["p_value"],
                output_format="pdf",
            ),
        },
        "downloads": {
            "D_csv_base64": _csv_base64(disappearance),
            "P_csv_base64": _csv_base64(product),
            "R_csv_base64": _csv_base64(resistant),
        },
        "notes": [
            "D/P/R 由上传的两个样品文件定义：D=上游有下游无，P=下游有上游无，R=上下游都有。",
            "选择的分子数据库只作为来源库，用于判断 D/P/R 分子是否存在于该来源库并进行卡方检验。",
            "如果勾选移除核心分子，系统会移除同时存在于上游、下游以及数据库所有来源文件交集中的分子；如果数据库不是由多个来源文件构成，则不会额外移除核心分子。",
        ],
    }


@router.post("/analyze")
async def analyze_source_database(
    upstream_file: UploadFile = File(...),
    source_file_1: UploadFile = File(...),
    source_file_2: UploadFile = File(...),
    downstream_file: UploadFile = File(...),
    source_name: str = Form("Source Database"),
):
    upstream = await _read_formula_set(upstream_file)
    source_1 = await _read_formula_set(source_file_1)
    source_2 = await _read_formula_set(source_file_2)
    downstream = await _read_formula_set(downstream_file)

    original_counts = {
        "upstream": len(upstream),
        "source_1": len(source_1),
        "source_2": len(source_2),
        "downstream": len(downstream),
    }

    core = upstream & source_1 & source_2 & downstream
    upstream -= core
    source_1 -= core
    source_2 -= core
    downstream -= core

    source_db = source_1 | source_2
    disappearance = upstream - downstream
    product = downstream - upstream
    resistant = upstream & downstream

    d_in = len(disappearance & source_db)
    d_out = len(disappearance - source_db)
    p_in = len(product & source_db)
    p_out = len(product - source_db)
    r_in = len(resistant & source_db)
    r_out = len(resistant - source_db)

    table_3x2 = [[d_in, d_out], [p_in, p_out], [r_in, r_out]]
    table_pvsd = [[p_in, p_out], [d_in, d_out]]
    table_dvsr = [[d_in, d_out], [r_in, r_out]]

    test_3x2 = _safe_chi2(table_3x2, "3x2")
    test_pvsd = _safe_chi2(table_pvsd, "P vs D")
    test_dvsr = _safe_chi2(table_dvsr, "D vs R")

    return {
        "source_name": source_name,
        "original_counts": original_counts,
        "core_removed": len(core),
        "post_counts": {
            "upstream": len(upstream),
            "source_1": len(source_1),
            "source_2": len(source_2),
            "downstream": len(downstream),
            "source_database": len(source_db),
        },
        "fate_counts": {
            "D": len(disappearance),
            "P": len(product),
            "R": len(resistant),
        },
        "presence": {
            "D": {"in_source": d_in, "not_in_source": d_out, "presence_rate": _rate(d_in, d_in + d_out)},
            "P": {"in_source": p_in, "not_in_source": p_out, "presence_rate": _rate(p_in, p_in + p_out)},
            "R": {"in_source": r_in, "not_in_source": r_out, "presence_rate": _rate(r_in, r_in + r_out)},
        },
        "tests": {
            "overall_3x2": test_3x2,
            "p_vs_d": test_pvsd,
            "d_vs_r": test_dvsr,
        },
        "plots": {
            "overall_3x2": _heatmap(
                table_3x2,
                ["MDecay (D)\nUpstream only", "Mpdct (P)\nDownstream only", "MBkgd (R)\nBoth"],
                "Molecular Fate vs. Source Database",
                test_3x2["p_value"],
            ),
            "d_vs_r": _heatmap(table_dvsr, ["MDecay (D)", "MBkgd (R)"], "Disappeared (D) vs. Resistant (R)", test_dvsr["p_value"]),
            "p_vs_d": _heatmap(table_pvsd, ["Mpdct (P)", "MDecay (D)"], "Produced (P) vs. Disappeared (D)", test_pvsd["p_value"]),
        },
        "source_database_csv_base64": _csv_base64(source_db),
    }
