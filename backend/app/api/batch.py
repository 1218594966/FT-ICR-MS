import html
import io
import json
import shutil
import zipfile
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import matplotlib.pyplot as plt
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.api.export import _draw_vankrevelen
from app.api.history import (
    _build_import_result,
    _complete_regular_analysis_csv,
    _json_safe,
    _read_csv_auto,
)
from app.config import settings

router = APIRouter(prefix="/api/batch", tags=["batch"])

WEIGHTED_LABELS = [
    "O/C", "H/C", "N/C", "S/C", "P/C", "AImod", "NOSC",
    "DBE-O", "DBE/C", "DBE/H", "DBE/O", "DBE",
]
ALLOWED_CATEGORY_ELEMENTS = ["N", "S", "P", "Cl"]


def _safe_stem(filename: str) -> str:
    stem = Path(filename or "file").stem.strip() or "file"
    keep = []
    for ch in stem:
        keep.append(ch if ch.isalnum() or ch in ("-", "_", ".", " ") else "_")
    return "".join(keep)[:120]


def _parse_category_elements(elements: str) -> list[str]:
    selected = []
    for elem in (elements or "N,S").split(","):
        elem = elem.strip()
        if elem in ALLOWED_CATEGORY_ELEMENTS and elem not in selected:
            selected.append(elem)
    return selected or ["N", "S"]


def _batch_dir(session_id: str) -> Path:
    if not session_id or any(ch in session_id for ch in "\\/.."):
        raise HTTPException(status_code=400, detail="Invalid batch session id")
    root = settings.RESULT_DIR / "batch" / session_id
    if not root.exists():
        raise HTTPException(status_code=404, detail="Batch session not found")
    return root


def _save_figure(fig, path: Path, fmt: str, dpi: int = 300):
    fig.savefig(path, format=fmt, dpi=dpi, transparent=False, bbox_inches="tight", pad_inches=0)
    plt.close(fig)


def _write_xlsx(path: Path, rows: list[list]):
    def col_name(idx: int) -> str:
        name = ""
        while idx:
            idx, rem = divmod(idx - 1, 26)
            name = chr(65 + rem) + name
        return name

    def cell_xml(row_idx: int, col_idx: int, value):
        ref = f"{col_name(col_idx)}{row_idx}"
        if isinstance(value, (int, float)) and value == value:
            return f'<c r="{ref}"><v>{value}</v></c>'
        text = html.escape("" if value is None else str(value))
        return f'<c r="{ref}" t="inlineStr"><is><t>{text}</t></is></c>'

    sheet_rows = []
    for r_idx, row in enumerate(rows, start=1):
        cells = "".join(cell_xml(r_idx, c_idx, value) for c_idx, value in enumerate(row, start=1))
        sheet_rows.append(f'<row r="{r_idx}">{cells}</row>')
    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<sheetData>{"".join(sheet_rows)}</sheetData></worksheet>'
    )
    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="Weighted Averages" sheetId="1" r:id="rId1"/></sheets></workbook>'
    )
    rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        '</Relationships>'
    )
    workbook_rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
        '</Relationships>'
    )
    content_types_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '</Types>'
    )

    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types_xml)
        zf.writestr("_rels/.rels", rels_xml)
        zf.writestr("xl/workbook.xml", workbook_xml)
        zf.writestr("xl/_rels/workbook.xml.rels", workbook_rels_xml)
        zf.writestr("xl/worksheets/sheet1.xml", sheet_xml)


@router.post("/regular-analysis")
async def batch_regular_analysis(
    files: list[UploadFile] = File(...),
    elements: str = Form("N,S"),
    custom_colors: str = Form(""),
    labeljson: str = Form("[]"),
):
    if not files:
        raise HTTPException(status_code=400, detail="请至少上传一个 CSV 文件")

    category_elements = _parse_category_elements(elements)
    try:
        parsed_labels = json.loads(labeljson or "[]")
        if not isinstance(parsed_labels, list):
            parsed_labels = []
    except json.JSONDecodeError:
        parsed_labels = []
    session_id = uuid4().hex
    root = settings.RESULT_DIR / "batch" / session_id
    upload_dir = root / "uploads"
    root.mkdir(parents=True, exist_ok=True)
    upload_dir.mkdir(parents=True, exist_ok=True)

    items = []
    weighted_rows = [["文件名", "处理后分子数", "分配率(%)", *WEIGHTED_LABELS]]
    try:
        for idx, file in enumerate(files, start=1):
            filename = Path(file.filename or f"file_{idx}.csv").name
            if not filename.lower().endswith(".csv"):
                items.append({"filename": filename, "status": "failed", "error": "仅支持 CSV 文件"})
                continue

            item_id = uuid4().hex[:12]
            stem = _safe_stem(filename)
            uploaded_path = upload_dir / f"{item_id}_{filename}"
            with uploaded_path.open("wb") as out:
                shutil.copyfileobj(file.file, out)

            try:
                raw_df = _read_csv_auto(uploaded_path)
                completed_df, steps, total_time = _complete_regular_analysis_csv(raw_df)
                csv_path = root / f"{item_id}_{stem}_completed.csv"
                completed_df.to_csv(csv_path, index=False, encoding="utf-8-sig")

                result = _build_import_result(
                    completed_df,
                    steps,
                    total_time,
                    str(csv_path),
                    category_elements=category_elements,
                )
                pseudo_task = SimpleNamespace(filename=stem, status="success", result=_json_safe(result))

                fs = result["steps"].get("full_search", {}).get("data", {})
                assignment_rate = fs.get("assignment_rate", 0)
                panel_label = ""
                if idx - 1 < len(parsed_labels):
                    panel_label = str(parsed_labels[idx - 1] or "").strip()[:80]
                svg_path = root / f"{item_id}_{stem}_vankrevelen.svg"
                pdf_path = root / f"{item_id}_{stem}_vankrevelen.pdf"
                _save_figure(
                    _draw_vankrevelen(pseudo_task, panel_label=panel_label, custom_colors=custom_colors),
                    svg_path,
                    "svg",
                    dpi=150,
                )
                _save_figure(
                    _draw_vankrevelen(pseudo_task, panel_label=panel_label, custom_colors=custom_colors),
                    pdf_path,
                    "pdf",
                    dpi=300,
                )

                weighted = result["steps"].get("weighted_avg", {}).get("data", {}).get("weighted_averages", {})
                weighted_rows.append([
                    filename,
                    len(completed_df),
                    assignment_rate,
                    *[weighted.get(f"{label}_w", "") for label in WEIGHTED_LABELS],
                ])
                items.append({
                    "id": item_id,
                    "filename": filename,
                    "status": "success",
                    "rows": len(completed_df),
                    "assignment_rate": assignment_rate,
                    "figure_label": panel_label,
                    "preview_url": f"/api/batch/{session_id}/preview/{item_id}",
                    "pdf_url": f"/api/batch/{session_id}/pdf/{item_id}",
                })
            except Exception as exc:
                items.append({"id": item_id, "filename": filename, "status": "failed", "error": str(exc)})

        successful = [item for item in items if item.get("status") == "success"]
        if successful:
            _write_xlsx(root / "weighted_averages.xlsx", weighted_rows)
            with zipfile.ZipFile(root / "vankrevelen_pdfs.zip", "w", compression=zipfile.ZIP_DEFLATED) as zf:
                for item in successful:
                    pdf = next(root.glob(f"{item['id']}_*_vankrevelen.pdf"), None)
                    if pdf:
                        zf.write(pdf, arcname=pdf.name)

        return {
            "session_id": session_id,
            "total": len(files),
            "success": len(successful),
            "failed": len(items) - len(successful),
            "category_elements": category_elements,
            "custom_colors": custom_colors,
            "figure_labels": parsed_labels,
            "items": items,
            "pdf_zip_url": f"/api/batch/{session_id}/pdf-zip" if successful else "",
            "weighted_excel_url": f"/api/batch/{session_id}/weighted-excel" if successful else "",
        }
    except Exception:
        shutil.rmtree(root, ignore_errors=True)
        raise


@router.get("/{session_id}/preview/{item_id}")
def get_preview(session_id: str, item_id: str):
    root = _batch_dir(session_id)
    path = next(root.glob(f"{item_id}_*_vankrevelen.svg"), None)
    if not path:
        raise HTTPException(status_code=404, detail="Preview not found")
    return FileResponse(path, media_type="image/svg+xml")


@router.get("/{session_id}/pdf/{item_id}")
def get_pdf(session_id: str, item_id: str):
    root = _batch_dir(session_id)
    path = next(root.glob(f"{item_id}_*_vankrevelen.pdf"), None)
    if not path:
        raise HTTPException(status_code=404, detail="PDF not found")
    return FileResponse(path, filename=path.name, media_type="application/pdf")


@router.get("/{session_id}/pdf-zip")
def get_pdf_zip(session_id: str):
    root = _batch_dir(session_id)
    path = root / "vankrevelen_pdfs.zip"
    if not path.exists():
        raise HTTPException(status_code=404, detail="PDF ZIP not found")
    return FileResponse(path, filename="vankrevelen_pdfs.zip", media_type="application/zip")


@router.get("/{session_id}/weighted-excel")
def get_weighted_excel(session_id: str):
    root = _batch_dir(session_id)
    path = root / "weighted_averages.xlsx"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Weighted Excel not found")
    return FileResponse(
        path,
        filename="weighted_averages.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
