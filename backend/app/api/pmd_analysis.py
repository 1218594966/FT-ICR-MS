import base64
import io
import json
import math
import re
import uuid
from pathlib import Path
from urllib.parse import quote

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.config import settings
from app.core.fonts import apply_font_to_figure, configure_matplotlib_fonts

router = APIRouter(prefix="/api/pmd", tags=["pmd-analysis"])

PMD_DIR = settings.RESULT_DIR / "pmd"
PMD_DIR.mkdir(parents=True, exist_ok=True)

MONO_MASS = {
    "C": 12.0,
    "H": 1.00782503223,
    "O": 15.99491461957,
    "N": 14.00307400443,
    "S": 31.9720711744,
    "P": 30.97376199842,
    "Cl": 34.968852682,
    "F": 18.99840316273,
}

DEFAULT_REACTIONS = [
    ("Carboxylic acid", "-", "CO", "#ef4444", "Loss of CO"),
    ("Carboxylic acid", "-", "CO2", "#ef4444", "Decarboxylation"),
    ("Carboxylic acid", "-", "CH2O", "#ef4444", "Loss of formaldehyde"),
    ("Oxygen addition", "+", "O", "#2563eb", "Hydroxylation"),
    ("Oxygen addition", "+", "O2", "#2563eb", "Two-hydroxylation"),
    ("Oxygen addition", "+", "O3", "#2563eb", "Tri-hydroxylation"),
    ("Oxygen addition", "+", "H2O", "#2563eb", "Hydration"),
    ("Oxygen addition", "+", "H2O2", "#2563eb", "Di-hydroxylation"),
    ("Other reactions", "-", "H2O", "#10b981", "Dehydration"),
    ("Other reactions", "+", "H2", "#10b981", "Hydrogenation"),
    ("Other reactions", "-", "H2", "#10b981", "Dehydrogenation"),
    ("Sulfate", "-", "S", "#9333ea", "Remove S"),
    ("Sulfate", "-", "SO", "#9333ea", "Remove SO"),
    ("Sulfate", "-", "SO2", "#9333ea", "Remove SO2"),
    ("Sulfate", "-", "SO3", "#9333ea", "Remove SO3"),
    ("Amine", "-", "NH3", "#f59e0b", "Ammonia elimination"),
    ("Amine", "-", "NH", "#f59e0b", "Deamination"),
    ("Dealkyl", "-", "CH2", "#64748b", "Demethylation"),
    ("Dealkyl", "-", "C2H2", "#64748b", "Dealkylation"),
    ("Dealkyl", "-", "C2H4", "#64748b", "Deethylation"),
    ("Dealkyl", "-", "C3H6", "#64748b", "Deisopropyl"),
]


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


def _find_col(df, candidates):
    normalized = _normalized_columns(df)
    for candidate in candidates:
        key = candidate.strip().lower().replace("_", " ")
        if key in normalized:
            return normalized[key]
    return None


def _parse_formula(formula: str):
    counts = {}
    for elem, count in re.findall(r"(Cl|[A-Z][a-z]?)(\d*)", str(formula or "")):
        if elem not in MONO_MASS:
            continue
        counts[elem] = counts.get(elem, 0) + (int(count) if count else 1)
    return counts


def _mass(formula: str):
    counts = _parse_formula(formula)
    if not counts:
        raise ValueError(f"Invalid formula: {formula}")
    return float(sum(MONO_MASS[e] * n for e, n in counts.items()))


def _load_molecules(upload: UploadFile, root: Path):
    safe_name = Path(upload.filename or "sample.csv").name
    path = root / safe_name
    path.write_bytes(upload.file.read())
    df = _read_csv_auto(path)
    formula_col = _find_col(df, ("Molecular Formula", "MolForm", "Formula"))
    if not formula_col:
        raise HTTPException(status_code=400, detail=f"{safe_name} must contain Molecular Formula or MolForm")
    intensity_col = _find_col(df, ("Peak Height", "PeakHeight", "Peak_Height", "Intensity", "Abundance"))
    clean = pd.DataFrame({"formula": df[formula_col].fillna("").astype(str).str.strip()})
    clean = clean[clean["formula"] != ""]
    if intensity_col:
        clean["intensity"] = pd.to_numeric(df.loc[clean.index, intensity_col], errors="coerce").fillna(0).clip(lower=0)
    else:
        clean["intensity"] = 1.0
    clean = clean.groupby("formula", as_index=False)["intensity"].sum()
    clean["mass"] = clean["formula"].map(_mass)
    return safe_name, clean


def _load_reactions(custom_reactions: str = ""):
    rows = []
    if custom_reactions:
        try:
            payload = json.loads(custom_reactions)
            if isinstance(payload, list):
                for item in payload:
                    rows.append((
                        item.get("category", "Custom"),
                        item.get("type", item.get("sign", "")),
                        item.get("formula", item.get("reaction", "")),
                        item.get("color", "#2563eb"),
                        item.get("name", item.get("label", item.get("reaction", ""))),
                    ))
        except Exception:
            rows = []
    if not rows:
        rows = DEFAULT_REACTIONS

    parsed = []
    for category, sign, formula, color, name in rows:
        if not formula:
            continue
        delta = _mass(formula)
        if str(sign).strip() == "-":
            delta = -delta
        elif str(sign).strip() not in ("+", ""):
            try:
                delta = float(sign)
            except ValueError:
                pass
        parsed.append({
            "category": str(category),
            "type": str(sign).strip(),
            "formula": str(formula),
            "color": str(color or "#2563eb"),
            "name": str(name or formula),
            "delta": float(delta),
        })
    return parsed


def _build_network(df_a, df_b, reactions, mode: str, round_val: int):
    graph = nx.DiGraph()
    cross = mode == "cross"
    left = df_a.copy()
    right = df_b.copy() if cross else df_a.copy()
    left["key"] = left["mass"].round(round_val)
    right["key"] = right["mass"].round(round_val)
    right_lookup = {}
    for row in right.to_dict("records"):
        right_lookup.setdefault(row["key"], []).append(row)

    for row in left.to_dict("records"):
        node_id = f"A:{row['formula']}" if cross else row["formula"]
        graph.add_node(node_id, formula=row["formula"], sample="A", mass=row["mass"], intensity=row["intensity"])
    for row in right.to_dict("records"):
        node_id = f"B:{row['formula']}" if cross else row["formula"]
        graph.add_node(node_id, formula=row["formula"], sample="B" if cross else "A", mass=row["mass"], intensity=row["intensity"])

    counts = {r["name"]: 0 for r in reactions}
    for src in left.to_dict("records"):
        src_id = f"A:{src['formula']}" if cross else src["formula"]
        for reaction in reactions:
            target_key = round(src["mass"] + reaction["delta"], round_val)
            for tgt in right_lookup.get(target_key, []):
                tgt_id = f"B:{tgt['formula']}" if cross else tgt["formula"]
                if src_id == tgt_id:
                    continue
                graph.add_edge(
                    src_id,
                    tgt_id,
                    reaction=reaction["name"],
                    category=reaction["category"],
                    formula=reaction["formula"],
                    delta=reaction["delta"],
                )
                counts[reaction["name"]] += 1
    return graph, counts


def _format_label(sign, formula):
    label = f"{sign}{formula}" if sign in ("+", "-") else formula
    return re.sub(r"([A-Za-z])(\d+)", r"\1$_{\2}$", label)


def _radar_figure(summary_df):
    configure_matplotlib_fonts("Times New Roman", pdf_fonttype=3)
    values = summary_df["Value"].astype(int).tolist()
    labels = [_format_label(row["Type"], row["Reaction"]) for _, row in summary_df.iterrows()]
    base_labels = (summary_df["Type"].astype(str) + "_" + summary_df["Reaction"].astype(str)).tolist()
    label_colors = dict(zip(base_labels, summary_df["Color"]))
    category_colors = dict(zip(summary_df["Category"], summary_df["Color"]))
    categories = summary_df["Category"].drop_duplicates().tolist()
    n = max(len(labels), 1)
    angles = np.linspace(0, 2 * np.pi, n, endpoint=False).tolist()
    fig, ax = plt.subplots(figsize=(16, 16), subplot_kw={"polar": True})
    plot_values = values + values[:1]
    plot_angles = angles + angles[:1]
    ax.plot(plot_angles, plot_values, color="dodgerblue", linewidth=2.5, marker="o", markersize=8)
    max_val = max(values) if values else 0
    tick_step = math.ceil(max_val / 4 / 50) * 50 if max_val > 0 else 10
    yticks = np.arange(0, max_val + tick_step, tick_step)
    ax.set_yticks(yticks)
    ax.set_yticklabels([str(int(y)) for y in yticks], color="grey", size=12)
    ax.set_ylim(0, max_val * 1.35 if max_val > 0 else 100)
    ax.set_xticks(angles)
    ax.set_xticklabels([])
    label_radius = ax.get_ylim()[1] * 1.08
    for angle, display, base in zip(angles, labels, base_labels):
        deg = np.rad2deg(angle)
        rotation = deg + 180 if 90 < deg < 270 else deg
        ha = "left" if 90 < deg < 270 else "right"
        txt = ax.text(angle, label_radius, display, size=13, color=label_colors.get(base, "black"),
                      fontweight="bold", rotation=rotation, ha=ha, va="center")
        txt.set_bbox(dict(facecolor="white", edgecolor="none", pad=0.2, alpha=0.65))
    start = 0
    counts_by_cat = summary_df["Category"].value_counts()
    for category in categories:
        count = int(counts_by_cat.get(category, 0))
        if count:
            mid = start + (count - 1) / 2.0
            angle = np.interp(mid, range(len(angles)), angles)
            deg = np.rad2deg(angle)
            rotation = deg - 90 if deg <= 180 else deg - 270
            ax.text(angle, ax.get_ylim()[1] * 1.24, category, size=20,
                    color=category_colors.get(category, "black"), ha="center", va="center",
                    rotation=rotation, fontweight="bold")
        start += count
    ax.grid(color="grey", linestyle="--", linewidth=0.5)
    apply_font_to_figure(fig)
    plt.tight_layout()
    return fig


def _save_fig(fig, path: Path, fmt: str):
    fig.savefig(path, format=fmt, dpi=300, bbox_inches="tight")
    plt.close(fig)


@router.post("/analyze")
async def analyze_pmd(
    file_a: UploadFile = File(...),
    file_b: UploadFile | None = File(None),
    mode: str = Form("single"),
    graph_format: str = Form("graphml"),
    round_val: int = Form(8),
    custom_reactions: str = Form(""),
):
    mode = "cross" if mode == "cross" and file_b is not None else "single"
    graph_format = "gexf" if graph_format == "gexf" else "graphml"
    round_val = max(4, min(int(round_val or 8), 10))
    session_id = uuid.uuid4().hex[:12]
    root = PMD_DIR / session_id
    root.mkdir(parents=True, exist_ok=True)

    name_a, df_a = _load_molecules(file_a, root)
    name_b, df_b = _load_molecules(file_b, root) if mode == "cross" else (name_a, df_a)
    reactions = _load_reactions(custom_reactions)
    graph, counts = _build_network(df_a, df_b, reactions, mode, round_val)

    summary_rows = []
    reaction_meta = {r["name"]: r for r in reactions}
    for name, value in counts.items():
        meta = reaction_meta[name]
        summary_rows.append({
            "Category": meta["category"],
            "Type": meta["type"],
            "Reaction": meta["formula"],
            "Name": name,
            "Value": int(value),
            "Color": meta["color"],
        })
    summary_df = pd.DataFrame(summary_rows)
    summary_csv = root / "reaction_counts.csv"
    summary_df.to_csv(summary_csv, index=False, encoding="utf-8-sig")

    graph_path = root / f"pmd_network.{graph_format}"
    if graph_format == "gexf":
        nx.write_gexf(graph, graph_path)
    else:
        nx.write_graphml(graph, graph_path)

    radar_png = root / "pmd_radar.png"
    radar_pdf = root / "pmd_radar.pdf"
    _save_fig(_radar_figure(summary_df), radar_png, "png")
    _save_fig(_radar_figure(summary_df), radar_pdf, "pdf")
    encoded = base64.b64encode(radar_png.read_bytes()).decode("utf-8")

    return {
        "session_id": session_id,
        "mode": mode,
        "sample_a": name_a,
        "sample_b": name_b if mode == "cross" else "",
        "nodes": graph.number_of_nodes(),
        "edges": graph.number_of_edges(),
        "reaction_counts": summary_df.to_dict(orient="records"),
        "radar_png": encoded,
        "downloads": {
            "graph": f"/api/pmd/{session_id}/download/{graph_path.name}",
            "counts_csv": f"/api/pmd/{session_id}/download/{summary_csv.name}",
            "radar_pdf": f"/api/pmd/{session_id}/download/{radar_pdf.name}",
            "radar_png": f"/api/pmd/{session_id}/download/{radar_png.name}",
        },
    }


@router.get("/{session_id}/download/{filename}")
def download_pmd(session_id: str, filename: str):
    if not re.fullmatch(r"[A-Za-z0-9_-]+", session_id or ""):
        raise HTTPException(status_code=400, detail="Invalid session id")
    safe_name = Path(filename).name
    path = PMD_DIR / session_id / safe_name
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(str(path), filename=quote(safe_name))
