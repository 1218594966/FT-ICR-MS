import os
import io
import re
import uuid
import math
import shutil
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
from pathlib import Path
from datetime import datetime
from fastapi import APIRouter, UploadFile, File, HTTPException, Form, Depends
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.models.database import get_db, Task
from app.core.fonts import configure_matplotlib_fonts

router = APIRouter(prefix="/api/data-analysis", tags=["data-analysis"])

UPLOAD_DIR = settings.UPLOAD_DIR / "data_analysis"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

CATEGORY_BOUNDARIES = {
    "Lipid": ((0, 0.3), (1.5, 2.0)),
    "Peptide-like": ((0.3, 0.67), (1.5, 2.2)),
    "Carbohydrate": ((0.67, 1.2), (1.5, 2.5)),
    "Unsaturated hydrocarbon": ((0, 0.1), (0.67, 1.5)),
    "Lignin": ((0.1, 0.67), (0.67, 1.5)),
    "Condensed aromatics": ((0, 0.67), (0.3, 0.67)),
    "Tannin": ((0.67, 1.2), (0.5, 1.5)),
}

MOLECULE_STYLES = {
    'Disappearance': {'color': '#FF3030', 'marker': 'o'},
    'Resistant': {'color': '#90EE90', 'marker': 's'},
    'Product': {'color': '#4D94FF', 'marker': '^'},
}


def _parse_molform(molform):
    if not isinstance(molform, str):
        return {'C': 0, 'H': 0, 'O': 0, 'N': 0, 'P': 0, 'S': 0}
    elements = re.findall(r'([A-Z][a-z]?)(\d*)', molform)
    counts = {'C': 0, 'H': 0, 'O': 0, 'N': 0, 'P': 0, 'S': 0}
    for elem, count in elements:
        if elem in counts:
            counts[elem] = int(count) if count else 1
    return counts


def _calc_metrics(molform):
    if not isinstance(molform, str):
        return {}
    elements = re.findall(r'([A-Z][a-z]?)(\d*)', molform)
    ec = {'C': 0, 'H': 0, 'O': 0, 'N': 0, 'P': 0, 'S': 0}
    for elem, count in elements:
        if elem in ec:
            ec[elem] = int(count) if count else 1
    C, H, O, N, P, S = ec['C'], ec['H'], ec['O'], ec['N'], ec['P'], ec['S']
    Cl, F = 0, 0
    m = {}
    m['H/C'] = H / C if C != 0 else np.nan
    m['O/C'] = O / C if C != 0 else np.nan
    DBE = (2 * C + N + P - H + 2) / 2
    m['DBE_O'] = DBE - O
    den = C - 0.5 * O - S - N - P
    m['AImod'] = (1 + C - 0.5 * O - S - 0.5 * H) / den if den != 0 else np.nan
    m['NOSC'] = -((4 * C + H - 3 * N - 2 * O + 5 * P - 2 * S - Cl - F) / C) + 4 if C != 0 else np.nan
    m['DBE/C'] = DBE / C if C != 0 else np.nan
    m['DBE/H'] = DBE / H if H != 0 else np.nan
    m['DBE/O'] = DBE / O if O != 0 else np.nan
    is_cram = 0
    if (0.30 <= m['DBE/C'] <= 0.68 and 0.20 <= m['DBE/H'] <= 0.95 and 0.77 <= m['DBE/O'] <= 1.75):
        is_cram = 1
    m['CRAM'] = is_cram
    return m


def _calc_hcoc(df):
    hc, oc = [], []
    for mol in df['MolForm']:
        e = _parse_molform(mol)
        hc.append(e['H'] / e['C'] if e['C'] > 0 else 0)
        oc.append(e['O'] / e['C'] if e['C'] > 0 else 0)
    df['H/C'] = hc
    df['O/C'] = oc
    return df


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
    for candidate in ("Peak Height", "PeakHeight", "Peak_Height", "Intensity", "intensity", "Abundance", "宄伴珮", "寮哄害"):
        key = candidate.strip().lower().replace("_", " ")
        if key in normalized:
            return normalized[key]
    return None


def _molecule_intensity_map(df, filename: str):
    formula_col = _find_formula_col(df)
    if not formula_col:
        raise HTTPException(status_code=400, detail=f"{filename} must contain Molecular Formula or MolForm")

    intensity_col = _find_intensity_col(df)
    clean = pd.DataFrame({"MolForm": df[formula_col].fillna("").astype(str).str.strip()})
    clean = clean[clean["MolForm"] != ""]
    if intensity_col:
        clean["intensity"] = pd.to_numeric(df.loc[clean.index, intensity_col], errors="coerce").fillna(0).clip(lower=0)
    else:
        clean["intensity"] = 1.0
    grouped = clean.groupby("MolForm", as_index=True)["intensity"].sum()
    return {str(formula): float(value) for formula, value in grouped.items()}


def _safe_session_id(session_id: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", session_id or ""):
        raise HTTPException(status_code=400, detail="Invalid session id")
    return session_id


def _load_dpr_dataframe(session_id: str, filename: str):
    session_id = _safe_session_id(session_id)
    filename = Path(filename).name
    fpath = UPLOAD_DIR / session_id / filename
    if not fpath.exists():
        raise HTTPException(status_code=404, detail="File not found")

    df = _read_csv_auto(fpath)
    if not all(c in df.columns for c in ['MolForm', 'Col1', 'Col2']):
        raise HTTPException(status_code=400, detail="Invalid CSV format")

    df['value'] = -1
    df.loc[(df['Col1'] == 1) & (df['Col2'] == 1), 'value'] = 1
    df.loc[(df['Col1'] == 1) & (df['Col2'] == 0), 'value'] = 0
    df.loc[(df['Col1'] == 0) & (df['Col2'] == 1), 'value'] = 2
    df = df[df['value'] != -1]
    df = _calc_hcoc(df)

    cat_map = {0: 'Disappearance', 1: 'Resistant', 2: 'Product'}
    df['molecule_category'] = df['value'].map(cat_map)
    return df


def _draw_dpr_figure(
    session_id: str,
    filename: str,
    category: str = "all",
    font_size: int = 16,
    scale: float = 1.0,
    panel_label: str = "",
    dot_size: float = 30,
    font_family: str = "Times New Roman",
):
    df = _load_dpr_dataframe(session_id, filename)

    configure_matplotlib_fonts(font_family or 'Times New Roman', pdf_fonttype=42)

    fs = {
        'axes_labels': font_size, 'tick_labels': font_size - 2,
        'legend': font_size - 2, 'panel_labels': font_size,
        'hist_tick_labels': font_size - 2,
    }
    for k in fs:
        fs[k] *= scale

    fig = plt.figure(figsize=(10 * scale, 8 * scale))
    gs = GridSpec(3, 3, height_ratios=[1, 4, 1], width_ratios=[4, 1, 0.5])
    ax_top = fig.add_subplot(gs[0, 0])
    ax_main = fig.add_subplot(gs[1, 0])
    ax_right = fig.add_subplot(gs[1, 1])
    ax_legend = fig.add_subplot(gs[0, 1])

    ax_main.set_xlim(0, 1.2)
    ax_main.set_ylim(0, 2.5)
    ax_top.set_xlim(0, 1.2)
    ax_right.set_ylim(0, 2.5)

    np.random.seed(42)
    jitter = 0.003
    df['O/C_j'] = df['O/C'] + np.random.normal(0, jitter, len(df))
    df['H/C_j'] = df['H/C'] + np.random.normal(0, jitter, len(df))

    ax_main.grid(True, linestyle='--', alpha=0.3, linewidth=0.5 * scale)
    for name, ((oc_min, oc_max), (hc_min, hc_max)) in CATEGORY_BOUNDARIES.items():
        lw = 0.5 * scale
        ax_main.plot([oc_min, oc_max], [hc_min, hc_min], 'k:', linewidth=lw)
        ax_main.plot([oc_min, oc_max], [hc_max, hc_max], 'k:', linewidth=lw)
        ax_main.plot([oc_min, oc_min], [hc_min, hc_max], 'k:', linewidth=lw)
        ax_main.plot([oc_max, oc_max], [hc_min, hc_max], 'k:', linewidth=lw)

    draw_order = ['Resistant', 'Disappearance', 'Product']
    cats = draw_order if category == 'all' else [category]

    for cat_name in cats:
        group = df[df['molecule_category'] == cat_name]
        if not group.empty:
            style = MOLECULE_STYLES[cat_name]
            ax_main.scatter(group['O/C_j'], group['H/C_j'], c=style['color'],
                            marker=style['marker'], s=dot_size * (scale ** 2),
                            alpha=0.8, edgecolors='none', linewidths=0.3 * scale, label=cat_name)

    bins_oc = np.linspace(0, 1.2, 30)
    bottom = np.zeros(len(bins_oc) - 1)
    for cat_name in cats:
        group = df[df['molecule_category'] == cat_name]
        if not group.empty:
            c, e = np.histogram(group['O/C'], bins=bins_oc)
            ax_top.bar(0.5 * (e[:-1] + e[1:]), c, width=e[1] - e[0],
                       alpha=0.8, color=MOLECULE_STYLES[cat_name]['color'], edgecolor='none', bottom=bottom)
            bottom += c

    bins_hc = np.linspace(0, 2.5, 30)
    left = np.zeros(len(bins_hc) - 1)
    for cat_name in cats:
        group = df[df['molecule_category'] == cat_name]
        if not group.empty:
            c, e = np.histogram(group['H/C'], bins=bins_hc)
            ax_right.barh(0.5 * (e[:-1] + e[1:]), c, height=e[1] - e[0],
                          alpha=0.8, color=MOLECULE_STYLES[cat_name]['color'], edgecolor='none', left=left)
            left += c

    ax_legend.axis('off')
    legend_elements = []
    for cat_name in cats:
        style = MOLECULE_STYLES[cat_name]
        count = len(df[df['molecule_category'] == cat_name])
        legend_elements.append(plt.Line2D([0], [0], marker=style['marker'], color='w',
                                          markerfacecolor=style['color'], markersize=10 * scale,
                                          markeredgecolor='black', markeredgewidth=0.5 * scale,
                                          label=f"{cat_name} (n = {count})"))
    leg = ax_legend.legend(handles=legend_elements, loc='center', frameon=True, fontsize=fs['legend'])
    leg.get_frame().set_edgecolor('black')
    leg.get_frame().set_linewidth(0.5 * scale)

    ax_main.set_xlabel('O/C', fontsize=fs['axes_labels'])
    ax_main.set_ylabel('H/C', fontsize=fs['axes_labels'])
    ax_main.tick_params(axis='both', labelsize=fs['tick_labels'])

    if panel_label:
        ax_top.text(0.02, 0.98, panel_label, transform=ax_top.transAxes,
                    fontsize=fs['panel_labels'], fontweight='bold', va='top', ha='left')

    ax_top.set_ylabel('Count', fontsize=fs['axes_labels'])
    ax_right.set_xlabel('Count', fontsize=fs['axes_labels'])
    ax_top.set_xticklabels([])
    ax_right.set_yticklabels([])

    for ax in [ax_top, ax_right]:
        for spine in ax.spines.values():
            spine.set_visible(False)
    ax_top.tick_params(axis='y', which='both', length=0, labelsize=fs['hist_tick_labels'])
    ax_right.tick_params(axis='x', which='both', length=0, labelsize=fs['hist_tick_labels'])

    plt.tight_layout()
    plt.subplots_adjust(hspace=0.05, wspace=0.05)
    return fig


def _stream_figure(fig, fmt: str, media_type: str, filename: str = None, attachment: bool = True, dpi: int = 300):
    buf = io.BytesIO()
    fig.savefig(buf, format=fmt, dpi=dpi, transparent=False, bbox_inches='tight', pad_inches=0)
    plt.close(fig)
    buf.seek(0)
    headers = {"Content-Disposition": f"attachment; filename={filename}"} if attachment and filename else {}
    return StreamingResponse(buf, media_type=media_type, headers=headers)



@router.post("/process")
async def process_csvs(
    file1: UploadFile = File(...),
    file2: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    session_id = str(uuid.uuid4())[:8]
    session_dir = UPLOAD_DIR / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    safe_file1 = Path(file1.filename or "file1.csv").name
    safe_file2 = Path(file2.filename or "file2.csv").name
    if safe_file1 == safe_file2:
        p = Path(safe_file2)
        safe_file2 = f"{p.stem}_2{p.suffix}"

    task = Task(
        id=session_id,
        filename=f"{safe_file1} & {safe_file2}",
        task_type="dpr",
        status="running",
        current_step="uploading",
        progress=0.0,
        upload_dir=str(session_dir),
    )
    db.add(task)
    db.commit()

    csv1_path = session_dir / safe_file1
    csv2_path = session_dir / safe_file2
    with open(csv1_path, "wb") as f:
        f.write(await file1.read())
    with open(csv2_path, "wb") as f:
        f.write(await file2.read())

    try:
        name1 = Path(safe_file1).stem
        name2 = Path(safe_file2).stem

        task.current_step = "reading_files"
        task.progress = 10.0
        db.commit()

        df1 = _read_csv_auto(csv1_path)
        df2 = _read_csv_auto(csv2_path)
        map1 = _molecule_intensity_map(df1, safe_file1)
        map2 = _molecule_intensity_map(df2, safe_file2)
        if not map1 or not map2:
            raise HTTPException(status_code=400, detail="Both files must contain at least one valid molecular formula")

        task.current_step = "building_matrix"
        task.progress = 50.0
        db.commit()

        formulas = sorted(set(map1) | set(map2))
        raw_t = pd.DataFrame({
            "MolForm": formulas,
            "Col1": [map1.get(formula, 0.0) for formula in formulas],
            "Col2": [map2.get(formula, 0.0) for formula in formulas],
        })
        binary_t = pd.DataFrame({
            "MolForm": formulas,
            "Col1": [1 if map1.get(formula, 0.0) > 0 else 0 for formula in formulas],
            "Col2": [1 if map2.get(formula, 0.0) > 0 else 0 for formula in formulas],
        })

        task.current_step = "calculating_metrics"
        task.progress = 70.0
        db.commit()

        metrics_df = pd.DataFrame(binary_t["MolForm"].apply(_calc_metrics).tolist())
        binary_final = pd.concat([binary_t, metrics_df], axis=1)

        def determine_dpr(row):
            if row["Col1"] == 1 and row["Col2"] == 0:
                return "D"
            if row["Col1"] == 0 and row["Col2"] == 1:
                return "P"
            if row["Col1"] == 1 and row["Col2"] == 1:
                return "R"
            return None

        binary_final["NewCol"] = binary_final.apply(determine_dpr, axis=1)

        raw_t_path = session_dir / f"transposed_raw_{name1}_{name2}.csv"
        binary_t_path = session_dir / f"transposed_binary_{name1}_{name2}.csv"
        final_path = session_dir / f"final_{name1}_{name2}.csv"
        raw_t.to_csv(raw_t_path, index=False, encoding="utf-8-sig")
        binary_t.to_csv(binary_t_path, index=False, encoding="utf-8-sig")
        binary_final.to_csv(final_path, index=False, encoding="utf-8-sig")

        task.status = "success"
        task.progress = 100.0
        task.current_step = "completed"
        task.finished_at = datetime.utcnow()
        task.csv_path = str(final_path)
        task.result = {
            "session_id": session_id,
            "name1": name1,
            "name2": name2,
            "raw_matrix_shape": [len(raw_t), 2],
            "binary_matrix_shape": [len(binary_t), 2],
            "columns": list(binary_final.columns),
            "final_file": f"final_{name1}_{name2}.csv",
        }
        db.commit()

        return {
            "session_id": session_id,
            "name1": name1,
            "name2": name2,
            "raw_matrix_shape": [len(raw_t), 2],
            "binary_matrix_shape": [len(binary_t), 2],
            "final_preview": binary_final.head(10).to_dict(orient="records"),
            "final_file": f"final_{name1}_{name2}.csv",
            "columns": list(binary_final.columns),
            "task_id": session_id,
        }
    except HTTPException as exc:
        task.status = "failed"
        task.error_message = str(exc.detail)
        task.finished_at = datetime.utcnow()
        db.commit()
        raise
    except Exception as exc:
        import traceback
        task.status = "failed"
        task.error_message = str(exc)
        task.finished_at = datetime.utcnow()
        db.commit()
        raise HTTPException(status_code=500, detail=f"{str(exc)}\n{traceback.format_exc()}")



@router.get("/download/{session_id}/{filename}")
def download_file(session_id: str, filename: str):
    session_id = _safe_session_id(session_id)
    filename = Path(filename).name
    fpath = UPLOAD_DIR / session_id / filename
    if not fpath.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path=str(fpath), filename=filename, media_type="text/csv")


@router.post("/upload-dpr-csv")
async def upload_dpr_csv(file: UploadFile = File(...)):
    session_id = str(uuid.uuid4())[:8]
    session_dir = UPLOAD_DIR / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    filename = Path(file.filename or "dpr.csv").name
    fpath = session_dir / filename
    await file.seek(0)
    with open(fpath, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return {"session_id": session_id, "filename": filename, "path": str(fpath)}


@router.get("/dpr-data/{session_id}/{filename}")
def get_dpr_data(session_id: str, filename: str):
    session_id = _safe_session_id(session_id)
    filename = Path(filename).name
    fpath = UPLOAD_DIR / session_id / filename
    if not fpath.exists():
        raise HTTPException(status_code=404, detail="File not found")

    df = _read_csv_auto(fpath)
    if not all(c in df.columns for c in ['MolForm', 'Col1', 'Col2']):
        raise HTTPException(status_code=400, detail="CSV must have columns: MolForm, Col1, Col2")

    df['value'] = -1
    df.loc[(df['Col1'] == 1) & (df['Col2'] == 1), 'value'] = 1
    df.loc[(df['Col1'] == 1) & (df['Col2'] == 0), 'value'] = 0
    df.loc[(df['Col1'] == 0) & (df['Col2'] == 1), 'value'] = 2
    df = df[df['value'] != -1]
    df = _calc_hcoc(df)

    cat_map = {0: 'Disappearance', 1: 'Resistant', 2: 'Product'}
    df['category'] = df['value'].map(cat_map)

    np.random.seed(42)
    jitter = 0.003
    df['O/C_j'] = df['O/C'] + np.random.normal(0, jitter, len(df))
    df['H/C_j'] = df['H/C'] + np.random.normal(0, jitter, len(df))

    result = {}
    for cat in ['Disappearance', 'Resistant', 'Product']:
        sub = df[df['category'] == cat]
        result[cat] = {
            'oc': sub['O/C_j'].tolist(),
            'hc': sub['H/C_j'].tolist(),
            'oc_raw': sub['O/C'].tolist(),
            'hc_raw': sub['H/C'].tolist(),
            'molform': sub['MolForm'].tolist(),
            'count': len(sub),
        }

    bins_oc = np.linspace(0, 1.2, 30)
    bins_hc = np.linspace(0, 2.5, 30)
    hist = {}
    for cat in ['Disappearance', 'Resistant', 'Product']:
        sub = df[df['category'] == cat]
        c_oc, _ = np.histogram(sub['O/C'], bins=bins_oc)
        c_hc, _ = np.histogram(sub['H/C'], bins=bins_hc)
        hist[cat] = {
            'oc_counts': c_oc.tolist(),
            'oc_edges': bins_oc.tolist(),
            'hc_counts': c_hc.tolist(),
            'hc_edges': bins_hc.tolist(),
        }

    return {
        'scatter': result,
        'histogram': hist,
        'total': len(df),
    }


@router.get("/export-pdf/{session_id}/{filename}")
def export_dpr_pdf(
    session_id: str,
    filename: str,
    category: str = "all",
    font_size: int = 16,
    scale: float = 1.0,
    panel_label: str = "",
    dot_size: float = 30,
    font_family: str = "Times New Roman",
):
    fig = _draw_dpr_figure(session_id, filename, category, font_size, scale, panel_label, dot_size, font_family)
    return _stream_figure(fig, "pdf", "application/pdf", f"DPR_{category}.pdf", attachment=True, dpi=300)

    session_id = _safe_session_id(session_id)
    filename = Path(filename).name
    fpath = UPLOAD_DIR / session_id / filename
    if not fpath.exists():
        raise HTTPException(status_code=404, detail="File not found")

    df = _read_csv_auto(fpath)
    if not all(c in df.columns for c in ['MolForm', 'Col1', 'Col2']):
        raise HTTPException(status_code=400, detail="Invalid CSV format")

    df['value'] = -1
    df.loc[(df['Col1'] == 1) & (df['Col2'] == 1), 'value'] = 1
    df.loc[(df['Col1'] == 1) & (df['Col2'] == 0), 'value'] = 0
    df.loc[(df['Col1'] == 0) & (df['Col2'] == 1), 'value'] = 2
    df = df[df['value'] != -1]
    df = _calc_hcoc(df)

    cat_map = {0: 'Disappearance', 1: 'Resistant', 2: 'Product'}
    df['molecule_category'] = df['value'].map(cat_map)

    configure_matplotlib_fonts('Times New Roman', pdf_fonttype=42)

    fs = {
        'axes_labels': font_size, 'tick_labels': font_size - 2,
        'legend': font_size - 2, 'panel_labels': font_size,
        'hist_tick_labels': font_size - 2,
    }
    for k in fs:
        fs[k] *= scale

    fig = plt.figure(figsize=(10 * scale, 8 * scale))
    gs = GridSpec(3, 3, height_ratios=[1, 4, 1], width_ratios=[4, 1, 0.5])
    ax_top = fig.add_subplot(gs[0, 0])
    ax_main = fig.add_subplot(gs[1, 0])
    ax_right = fig.add_subplot(gs[1, 1])
    ax_legend = fig.add_subplot(gs[0, 1])

    ax_main.set_xlim(0, 1.2)
    ax_main.set_ylim(0, 2.5)
    ax_top.set_xlim(0, 1.2)
    ax_right.set_ylim(0, 2.5)

    np.random.seed(42)
    jitter = 0.003
    df['O/C_j'] = df['O/C'] + np.random.normal(0, jitter, len(df))
    df['H/C_j'] = df['H/C'] + np.random.normal(0, jitter, len(df))

    ax_main.grid(True, linestyle='--', alpha=0.3, linewidth=0.5 * scale)

    for name, ((oc_min, oc_max), (hc_min, hc_max)) in CATEGORY_BOUNDARIES.items():
        lw = 0.5 * scale
        ax_main.plot([oc_min, oc_max], [hc_min, hc_min], 'k:', linewidth=lw)
        ax_main.plot([oc_min, oc_max], [hc_max, hc_max], 'k:', linewidth=lw)
        ax_main.plot([oc_min, oc_min], [hc_min, hc_max], 'k:', linewidth=lw)
        ax_main.plot([oc_max, oc_max], [hc_min, hc_max], 'k:', linewidth=lw)

    draw_order = ['Resistant', 'Disappearance', 'Product']
    cats = draw_order if category == 'all' else [category]

    for cat_name in cats:
        group = df[df['molecule_category'] == cat_name]
        if not group.empty:
            style = MOLECULE_STYLES[cat_name]
            ax_main.scatter(group['O/C_j'], group['H/C_j'], c=style['color'],
                           marker=style['marker'], s=dot_size * (scale ** 2),
                           alpha=0.8, edgecolors='none', linewidths=0.3 * scale, label=cat_name)

    bins_oc = np.linspace(0, 1.2, 30)
    bottom = np.zeros(len(bins_oc) - 1)
    for cat_name in cats:
        group = df[df['molecule_category'] == cat_name]
        if not group.empty:
            c, e = np.histogram(group['O/C'], bins=bins_oc)
            ax_top.bar(0.5 * (e[:-1] + e[1:]), c, width=e[1] - e[0],
                      alpha=0.8, color=MOLECULE_STYLES[cat_name]['color'], edgecolor='none', bottom=bottom)
            bottom += c

    bins_hc = np.linspace(0, 2.5, 30)
    left = np.zeros(len(bins_hc) - 1)
    for cat_name in cats:
        group = df[df['molecule_category'] == cat_name]
        if not group.empty:
            c, e = np.histogram(group['H/C'], bins=bins_hc)
            ax_right.barh(0.5 * (e[:-1] + e[1:]), c, height=e[1] - e[0],
                         alpha=0.8, color=MOLECULE_STYLES[cat_name]['color'], edgecolor='none', left=left)
            left += c

    ax_legend.axis('off')
    legend_elements = []
    for cat_name in cats:
        style = MOLECULE_STYLES[cat_name]
        count = len(df[df['molecule_category'] == cat_name])
        legend_elements.append(plt.Line2D([0], [0], marker=style['marker'], color='w',
                              markerfacecolor=style['color'], markersize=10 * scale,
                              markeredgecolor='black', markeredgewidth=0.5 * scale,
                              label=f"{cat_name} (n = {count})"))
    leg = ax_legend.legend(handles=legend_elements, loc='center', frameon=True, fontsize=fs['legend'])
    leg.get_frame().set_edgecolor('black')
    leg.get_frame().set_linewidth(0.5 * scale)

    ax_main.set_xlabel('O/C', fontsize=fs['axes_labels'])
    ax_main.set_ylabel('H/C', fontsize=fs['axes_labels'])
    ax_main.tick_params(axis='both', labelsize=fs['tick_labels'])

    if panel_label:
        ax_top.text(0.02, 0.98, panel_label, transform=ax_top.transAxes,
                    fontsize=fs['panel_labels'], fontweight='bold', va='top', ha='left')

    ax_top.set_ylabel('Count', fontsize=fs['axes_labels'])
    ax_right.set_xlabel('Count', fontsize=fs['axes_labels'])
    ax_top.set_xticklabels([])
    ax_right.set_yticklabels([])

    for ax in [ax_top, ax_right]:
        for spine in ax.spines.values():
            spine.set_visible(False)
    ax_top.tick_params(axis='y', which='both', length=0, labelsize=fs['hist_tick_labels'])
    ax_right.tick_params(axis='x', which='both', length=0, labelsize=fs['hist_tick_labels'])

    plt.tight_layout()
    plt.subplots_adjust(hspace=0.05, wspace=0.05)

    buf = io.BytesIO()
    fig.savefig(buf, format='pdf', dpi=300, transparent=False, bbox_inches='tight', pad_inches=0)
    plt.close(fig)
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/pdf",
                            headers={"Content-Disposition": f"attachment; filename=DPR_{category}.pdf"})


@router.get("/export-tif/{session_id}/{filename}")
def export_dpr_tif(
    session_id: str, filename: str, category: str = "all",
    font_size: int = 16, scale: float = 1.0, panel_label: str = "", dot_size: float = 30,
    font_family: str = "Times New Roman",
):
    fig = _draw_dpr_figure(session_id, filename, category, font_size, scale, panel_label, dot_size, font_family)
    return _stream_figure(fig, "tiff", "image/tiff", f"DPR_{category}.tif", attachment=True, dpi=300)

    session_id = _safe_session_id(session_id)
    filename = Path(filename).name
    fpath = UPLOAD_DIR / session_id / filename
    if not fpath.exists():
        raise HTTPException(status_code=404, detail="File not found")

    df = _read_csv_auto(fpath)
    if not all(c in df.columns for c in ['MolForm', 'Col1', 'Col2']):
        raise HTTPException(status_code=400, detail="Invalid CSV format")

    df['value'] = -1
    df.loc[(df['Col1'] == 1) & (df['Col2'] == 1), 'value'] = 1
    df.loc[(df['Col1'] == 1) & (df['Col2'] == 0), 'value'] = 0
    df.loc[(df['Col1'] == 0) & (df['Col2'] == 1), 'value'] = 2
    df = df[df['value'] != -1]
    df = _calc_hcoc(df)

    cat_map = {0: 'Disappearance', 1: 'Resistant', 2: 'Product'}
    df['molecule_category'] = df['value'].map(cat_map)

    configure_matplotlib_fonts('Times New Roman', pdf_fonttype=42)

    fs = {'axes_labels': font_size, 'tick_labels': font_size - 2, 'legend': font_size - 2,
          'panel_labels': font_size, 'hist_tick_labels': font_size - 2}
    for k in fs:
        fs[k] *= scale

    fig = plt.figure(figsize=(10 * scale, 8 * scale))
    gs = GridSpec(3, 3, height_ratios=[1, 4, 1], width_ratios=[4, 1, 0.5])
    ax_top = fig.add_subplot(gs[0, 0])
    ax_main = fig.add_subplot(gs[1, 0])
    ax_right = fig.add_subplot(gs[1, 1])
    ax_legend = fig.add_subplot(gs[0, 1])

    ax_main.set_xlim(0, 1.2)
    ax_main.set_ylim(0, 2.5)
    ax_top.set_xlim(0, 1.2)
    ax_right.set_ylim(0, 2.5)

    np.random.seed(42)
    jitter = 0.003
    df['O/C_j'] = df['O/C'] + np.random.normal(0, jitter, len(df))
    df['H/C_j'] = df['H/C'] + np.random.normal(0, jitter, len(df))

    ax_main.grid(True, linestyle='--', alpha=0.3, linewidth=0.5 * scale)
    for name, ((oc_min, oc_max), (hc_min, hc_max)) in CATEGORY_BOUNDARIES.items():
        lw = 0.5 * scale
        ax_main.plot([oc_min, oc_max], [hc_min, hc_min], 'k:', linewidth=lw)
        ax_main.plot([oc_min, oc_max], [hc_max, hc_max], 'k:', linewidth=lw)
        ax_main.plot([oc_min, oc_min], [hc_min, hc_max], 'k:', linewidth=lw)
        ax_main.plot([oc_max, oc_max], [hc_min, hc_max], 'k:', linewidth=lw)

    draw_order = ['Resistant', 'Disappearance', 'Product']
    cats = draw_order if category == 'all' else [category]

    for cat_name in cats:
        group = df[df['molecule_category'] == cat_name]
        if not group.empty:
            style = MOLECULE_STYLES[cat_name]
            ax_main.scatter(group['O/C_j'], group['H/C_j'], c=style['color'],
                           marker=style['marker'], s=dot_size * (scale ** 2),
                           alpha=0.8, edgecolors='none', linewidths=0.3 * scale, label=cat_name)

    bins_oc = np.linspace(0, 1.2, 30)
    bottom = np.zeros(len(bins_oc) - 1)
    for cat_name in cats:
        group = df[df['molecule_category'] == cat_name]
        if not group.empty:
            c, e = np.histogram(group['O/C'], bins=bins_oc)
            ax_top.bar(0.5 * (e[:-1] + e[1:]), c, width=e[1] - e[0],
                      alpha=0.8, color=MOLECULE_STYLES[cat_name]['color'], edgecolor='none', bottom=bottom)
            bottom += c

    bins_hc = np.linspace(0, 2.5, 30)
    left = np.zeros(len(bins_hc) - 1)
    for cat_name in cats:
        group = df[df['molecule_category'] == cat_name]
        if not group.empty:
            c, e = np.histogram(group['H/C'], bins=bins_hc)
            ax_right.barh(0.5 * (e[:-1] + e[1:]), c, height=e[1] - e[0],
                         alpha=0.8, color=MOLECULE_STYLES[cat_name]['color'], edgecolor='none', left=left)
            left += c

    ax_legend.axis('off')
    legend_elements = []
    for cat_name in cats:
        style = MOLECULE_STYLES[cat_name]
        count = len(df[df['molecule_category'] == cat_name])
        legend_elements.append(plt.Line2D([0], [0], marker=style['marker'], color='w',
                              markerfacecolor=style['color'], markersize=10 * scale,
                              markeredgecolor='black', markeredgewidth=0.5 * scale,
                              label=f"{cat_name} (n = {count})"))
    leg = ax_legend.legend(handles=legend_elements, loc='center', frameon=True, fontsize=fs['legend'])
    leg.get_frame().set_edgecolor('black')
    leg.get_frame().set_linewidth(0.5 * scale)

    ax_main.set_xlabel('O/C', fontsize=fs['axes_labels'])
    ax_main.set_ylabel('H/C', fontsize=fs['axes_labels'])
    ax_main.tick_params(axis='both', labelsize=fs['tick_labels'])
    if panel_label:
        ax_top.text(0.02, 0.98, panel_label, transform=ax_top.transAxes,
                    fontsize=fs['panel_labels'], fontweight='bold', va='top', ha='left')
    ax_top.set_ylabel('Count', fontsize=fs['axes_labels'])
    ax_right.set_xlabel('Count', fontsize=fs['axes_labels'])
    ax_top.set_xticklabels([])
    ax_right.set_yticklabels([])
    for ax in [ax_top, ax_right]:
        for spine in ax.spines.values():
            spine.set_visible(False)
    ax_top.tick_params(axis='y', which='both', length=0, labelsize=fs['hist_tick_labels'])
    ax_right.tick_params(axis='x', which='both', length=0, labelsize=fs['hist_tick_labels'])
    plt.tight_layout()
    plt.subplots_adjust(hspace=0.05, wspace=0.05)

    buf = io.BytesIO()
    fig.savefig(buf, format='tiff', dpi=300, transparent=False, bbox_inches='tight', pad_inches=0)
    plt.close(fig)
    buf.seek(0)
    return StreamingResponse(buf, media_type="image/tiff",
                            headers={"Content-Disposition": f"attachment; filename=DPR_{category}.tif"})


@router.get("/export-svg/{session_id}/{filename}")
def export_dpr_svg(
    session_id: str,
    filename: str,
    category: str = "all",
    font_size: int = 16,
    scale: float = 1.0,
    panel_label: str = "",
    dot_size: float = 30,
    font_family: str = "Times New Roman",
):
    fig = _draw_dpr_figure(session_id, filename, category, font_size, scale, panel_label, dot_size, font_family)
    return _stream_figure(fig, "svg", "image/svg+xml", attachment=False, dpi=150)
