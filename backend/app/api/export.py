import os
import io
import math
import re
from urllib.parse import quote
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pathlib import Path
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.models.database import get_db, Task
from app.config import settings

router = APIRouter(prefix="/api/export", tags=["export"])


def _attachment(filename: str) -> dict:
    safe_name = quote(filename or "export")
    return {"Content-Disposition": f"attachment; filename*=UTF-8''{safe_name}"}


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


CATEGORY_BOUNDARIES = {
    "Lipid": ((0, 0.3), (1.5, 2.0)),
    "Peptide-like": ((0.3, 0.67), (1.5, 2.2)),
    "Carbohydrate": ((0.67, 1.2), (1.5, 2.5)),
    "Unsaturated hydrocarbon": ((0, 0.1), (0.67, 1.5)),
    "Lignin": ((0.1, 0.67), (0.67, 1.5)),
    "Condensed aromatics": ((0, 0.67), (0.3, 0.67)),
    "Tannin": ((0.67, 1.2), (0.5, 1.5)),
}

ELEM_CATEGORY_MAP = {
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

ELEM_COLORS = {
    "CHO": "lightsalmon", "CHON": "royalblue", "CHOS": "crimson",
    "CHONS": "mediumturquoise", "CHONPS": "darkgrey", "CHOPS": "darkgrey",
    "CHONP": "darkgrey", "CHOP": "darkgrey",
    "CHOCl": "orange", "CHONCl": "steelblue", "CHOSCl": "darkred", "CHONSCl": "teal",
    "Other": "darkgrey",
}


def _normalize_elem_category(category: str) -> str:
    if not isinstance(category, str) or not category:
        return "Other"
    if category in ELEM_COLORS:
        return category

    tokens = re.findall(r"Cl|[A-Z][a-z]?", category)
    if not tokens and set(category).issubset(set("CHONPS")):
        tokens = list(category)
    elems = set(tokens)
    if "C" not in elems or "H" not in elems or "O" not in elems:
        return "Other"
    return ELEM_CATEGORY_MAP.get(frozenset(elems), "Other")


def _classify_elem(row):
    elems = set()
    for e in ["C", "H", "O", "N", "S", "P"]:
        if row.get(e, 0) > 0:
            elems.add(e)
    return ELEM_CATEGORY_MAP.get(frozenset(elems), "Other")


def _get_color_map(custom_colors: str = None):
    """Get color map, optionally with custom colors from frontend"""
    color_map = ELEM_COLORS.copy()
    if custom_colors:
        try:
            # Parse custom colors format: "CHO:#ff0000,CHON:#00ff00,..."
            for pair in custom_colors.split(','):
                if ':' in pair:
                    cat, color = pair.split(':', 1)
                    normalized_cat = _normalize_elem_category(cat)
                    if normalized_cat in color_map:
                        color_map[normalized_cat] = color
        except:
            pass
    return color_map


def _set_vector_font(font_size: int, scale: float):
    matplotlib.rcParams['font.family'] = 'Times New Roman'
    matplotlib.rcParams['pdf.fonttype'] = 3
    matplotlib.rcParams['ps.fonttype'] = 3
    matplotlib.rcParams['svg.fonttype'] = 'none'
    return font_size * scale


def _get_vk_arrays(task: Task):
    steps = task.result.get("steps", {})
    vk = steps.get("full_search", {}).get("data", {})
    oc_arr = vk.get("oc", [])
    hc_arr = vk.get("hc", [])
    elem_cat = vk.get("elem_category", [])
    if not oc_arr or not hc_arr:
        raise HTTPException(status_code=400, detail="No Van Krevelen data")

    valid = [
        (o, h, _normalize_elem_category(c))
        for o, h, c in zip(oc_arr, hc_arr, elem_cat)
        if isinstance(o, (int, float)) and isinstance(h, (int, float))
        and math.isfinite(o) and math.isfinite(h)
    ]
    if not valid:
        raise HTTPException(status_code=400, detail="No valid data points")

    return [v[0] for v in valid], [v[1] for v in valid], [v[2] for v in valid]


def _draw_vankrevelen(
    task: Task,
    font_size: int = 16,
    scale: float = 1.0,
    oc_min: float = 0,
    oc_max: float = 1.2,
    hc_min: float = 0.25,
    hc_max: float = 2.5,
    dot_size: float = 15,
    show_labels: bool = True,
    show_boundaries: bool = True,
    panel_label: str = "",
    custom_colors: str = None,
):
    oc_vals, hc_vals, cat_vals = _get_vk_arrays(task)
    color_map = _get_color_map(custom_colors)
    fs = _set_vector_font(font_size, scale)

    fig, ax = plt.subplots(figsize=(10 * scale, 8 * scale))

    if show_boundaries:
        for name, (oc_range, hc_range) in CATEGORY_BOUNDARIES.items():
            oc_min_b, oc_max_b = oc_range
            hc_min_b, hc_max_b = hc_range
            lw = 0.5 * scale
            ax.plot([oc_min_b, oc_max_b], [hc_min_b, hc_min_b], 'k:', linewidth=lw)
            ax.plot([oc_min_b, oc_max_b], [hc_max_b, hc_max_b], 'k:', linewidth=lw)
            ax.plot([oc_min_b, oc_min_b], [hc_min_b, hc_max_b], 'k:', linewidth=lw)
            ax.plot([oc_max_b, oc_max_b], [hc_min_b, hc_max_b], 'k:', linewidth=lw)
            if show_labels:
                lx = (oc_min_b + oc_max_b) / 2
                ly = (hc_min_b + hc_max_b) / 2
                rot = 0
                if name == "Unsaturated hydrocarbon":
                    rot = 90
                    ly -= 0.1
                ax.text(lx, ly, name, color='black', fontsize=fs - 2,
                        ha='center', va='center', rotation=rot)

    colors = [color_map.get(c, color_map["Other"]) for c in cat_vals]
    ax.scatter(oc_vals, hc_vals, c=colors, s=dot_size * (scale ** 2),
               marker='o', alpha=0.5, edgecolors='white', linewidths=0.5 * scale)

    ax.set_xlabel('O/C', fontsize=fs, fontweight='bold')
    ax.set_ylabel('H/C', fontsize=fs, fontweight='bold')
    ax.set_xlim(oc_min, oc_max)
    ax.set_ylim(hc_min, hc_max)

    if panel_label:
        ax.text(0.02, 0.98, panel_label, transform=ax.transAxes,
                fontsize=fs, fontweight='bold', va='top', ha='left')

    ax.grid(False)
    for spine in ax.spines.values():
        spine.set_edgecolor('black')
        spine.set_linewidth(0.5 * scale)
    ax.tick_params(axis='both', which='major', labelsize=fs - 2, direction='in')

    present_cats = sorted(set(cat_vals))
    legend_handles = [
        plt.Line2D([0], [0], marker='o', color='w', label=cat,
                   markerfacecolor=color_map.get(cat, '#999'),
                   markersize=10 * scale, linestyle='None')
        for cat in present_cats
    ]
    y_min, y_max = ax.get_ylim()
    y_frac = (1.8 - y_min) / (y_max - y_min) if y_max != y_min else 1
    leg = ax.legend(handles=legend_handles, labels=present_cats,
                    loc='upper right', bbox_to_anchor=(1, y_frac),
                    frameon=True, fontsize=fs - 2)
    leg.get_frame().set_edgecolor('black')
    leg.get_frame().set_linewidth(0.5 * scale)

    return fig


def _draw_standard_chart(task: Task, chart_type: str, font_size: int = 16, scale: float = 1.0):
    if task.status != "success" or not task.result:
        raise HTTPException(status_code=400, detail="No results")

    fs = _set_vector_font(font_size, scale)
    steps = task.result.get("steps", {})
    fig, ax = plt.subplots(figsize=(10 * scale, 6 * scale))

    if chart_type == "spectrum":
        d = steps.get("peak_detection", {}).get("data", {})
        mz = _sanitize(d.get("mz", []))
        abundance = _sanitize(d.get("abundance", []))
        points = [(x, y) for x, y in zip(mz, abundance) if isinstance(x, (int, float)) and isinstance(y, (int, float))]
        if not points:
            raise HTTPException(status_code=400, detail="No spectrum data")
        ax.plot([p[0] for p in points], [p[1] for p in points], color="#3b82f6", linewidth=0.8 * scale)
        ax.set_xlabel("m/z", fontsize=fs)
        ax.set_ylabel("Abundance", fontsize=fs)

    elif chart_type == "preliminary":
        d = steps.get("preliminary_search", {}).get("data", {})
        mz = _sanitize(d.get("mz", []))
        ppm = _sanitize(d.get("ppm_error", []))
        points = [(x, y) for x, y in zip(mz, ppm) if isinstance(x, (int, float)) and isinstance(y, (int, float))]
        if not points:
            raise HTTPException(status_code=400, detail="No preliminary search data")
        ax.scatter([p[0] for p in points], [p[1] for p in points], s=8 * (scale ** 2),
                   color="#f59e0b", edgecolors="none", alpha=0.8)
        ax.set_xlabel("m/z", fontsize=fs)
        ax.set_ylabel("Error (ppm)", fontsize=fs)

    elif chart_type == "class":
        data = steps.get("classification", {}).get("data", {}).get("type_counts", {})
        if not data:
            raise HTTPException(status_code=400, detail="No classification data")
        colors = ['#3b82f6', '#06b6d4', '#10b981', '#f59e0b', '#8b5cf6', '#ef4444', '#ec4899', '#64748b']
        labels = list(data.keys())
        values = list(data.values())
        wedges, _ = ax.pie(values, startangle=90, colors=colors[:len(values)],
                           wedgeprops={"linewidth": 0.8, "edgecolor": "white"})
        ax.legend(wedges, labels, loc="center left", bbox_to_anchor=(1, 0.5), fontsize=fs - 2)
        ax.set_aspect("equal")

    elif chart_type == "weighted":
        data = steps.get("weighted_avg", {}).get("data", {}).get("weighted_averages", {})
        if not data:
            raise HTTPException(status_code=400, detail="No weighted average data")
        labels = [k.replace("_w", "") for k in data.keys()]
        values = [v if isinstance(v, (int, float)) and math.isfinite(v) else 0 for v in data.values()]
        ax.bar(labels, values, color="#3b82f6")
        ax.set_ylabel("Weighted average", fontsize=fs)
        ax.tick_params(axis='x', labelrotation=30)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown chart type: {chart_type}")

    if chart_type != "class":
        ax.grid(True, linestyle="--", linewidth=0.5 * scale, alpha=0.25)
    ax.tick_params(axis='both', which='major', labelsize=fs - 2)
    for spine in ax.spines.values():
        spine.set_linewidth(0.5 * scale)
    fig.tight_layout()
    return fig


def _stream_figure(fig, fmt: str, filename: str, media_type: str, dpi: int = 300, attachment: bool = True):
    buf = io.BytesIO()
    fig.savefig(buf, format=fmt, dpi=dpi, transparent=False, bbox_inches='tight', pad_inches=0)
    plt.close(fig)
    buf.seek(0)
    headers = _attachment(filename) if attachment else {}
    return StreamingResponse(buf, media_type=media_type, headers=headers)


@router.get("/{task_id}/vankrevelen/pdf")
def export_vankrevelen_pdf(
    task_id: str,
    font_size: int = 16,
    scale: float = 1.0,
    oc_min: float = 0,
    oc_max: float = 1.2,
    hc_min: float = 0.25,
    hc_max: float = 2.5,
    dot_size: float = 15,
    show_labels: bool = True,
    show_boundaries: bool = True,
    panel_label: str = "",
    custom_colors: str = None,
    db: Session = Depends(get_db),
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status != "success" or not task.result:
        raise HTTPException(status_code=400, detail="No results")

    filename = f"{task.filename}_vankrevelen.pdf" if task.filename else "vankrevelen.pdf"
    fig = _draw_vankrevelen(
        task, font_size, scale, oc_min, oc_max, hc_min, hc_max, dot_size,
        show_labels, show_boundaries, panel_label, custom_colors,
    )
    return _stream_figure(fig, "pdf", filename, "application/pdf", dpi=300)


@router.get("/{task_id}/vankrevelen/svg")
def export_vankrevelen_svg(
    task_id: str,
    font_size: int = 16,
    scale: float = 1.0,
    oc_min: float = 0,
    oc_max: float = 1.2,
    hc_min: float = 0.25,
    hc_max: float = 2.5,
    dot_size: float = 15,
    show_labels: bool = True,
    show_boundaries: bool = True,
    panel_label: str = "",
    custom_colors: str = None,
    db: Session = Depends(get_db),
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status != "success" or not task.result:
        raise HTTPException(status_code=400, detail="No results")

    fig = _draw_vankrevelen(
        task, font_size, scale, oc_min, oc_max, hc_min, hc_max, dot_size,
        show_labels, show_boundaries, panel_label, custom_colors,
    )
    return _stream_figure(fig, "svg", "vankrevelen.svg", "image/svg+xml", dpi=150, attachment=False)


@router.get("/{task_id}/vankrevelen/tif")
def export_vankrevelen_tif(
    task_id: str,
    font_size: int = 16,
    scale: float = 1.0,
    oc_min: float = 0,
    oc_max: float = 1.2,
    hc_min: float = 0.25,
    hc_max: float = 2.5,
    dot_size: float = 15,
    show_labels: bool = True,
    show_boundaries: bool = True,
    panel_label: str = "",
    custom_colors: str = None,
    db: Session = Depends(get_db),
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status != "success" or not task.result:
        raise HTTPException(status_code=400, detail="No results")

    filename = f"{task.filename}_vankrevelen.tif" if task.filename else "vankrevelen.tif"
    fig = _draw_vankrevelen(
        task, font_size, scale, oc_min, oc_max, hc_min, hc_max, dot_size,
        show_labels, show_boundaries, panel_label, custom_colors,
    )
    return _stream_figure(fig, "tiff", filename, "image/tiff", dpi=600)


@router.get("/{task_id}/{chart_type}/pdf")
def export_chart_pdf(
    task_id: str,
    chart_type: str,
    font_size: int = 16,
    scale: float = 1.0,
    db: Session = Depends(get_db),
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    fig = _draw_standard_chart(task, chart_type, font_size, scale)
    filename = f"{task.filename}_{chart_type}.pdf" if task.filename else f"{chart_type}.pdf"
    return _stream_figure(fig, "pdf", filename, "application/pdf", dpi=300)


@router.get("/{task_id}/{chart_type}/tif")
def export_chart_tif(
    task_id: str,
    chart_type: str,
    font_size: int = 16,
    scale: float = 1.0,
    db: Session = Depends(get_db),
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    fig = _draw_standard_chart(task, chart_type, font_size, scale)
    filename = f"{task.filename}_{chart_type}.tif" if task.filename else f"{chart_type}.tif"
    return _stream_figure(fig, "tiff", filename, "image/tiff", dpi=600)
