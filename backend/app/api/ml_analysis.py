import base64
import io
import json
import math
import os
import re
import time
import unicodedata
from pathlib import Path
from typing import List, Optional

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.models.database import get_db, Task
from app.core.fonts import apply_font_to_figure, configure_matplotlib_fonts

router = APIRouter(prefix="/api/ml", tags=["ml-analysis"])


def _configure_ml_plot_fonts():
    configure_matplotlib_fonts("Times New Roman", pdf_fonttype=42)


def _clean_feature_label(label) -> str:
    text = unicodedata.normalize("NFKC", str(label or "")).strip()
    text = re.sub(r"[\u200b-\u200f\u202a-\u202e\ufeff]", "", text)
    text = text.replace("／", "/").replace("⁄", "/").replace("∕", "/")
    text = text.replace("－", "-").replace("–", "-").replace("—", "-")
    text = re.sub(r"\s+", " ", text)
    compact = text.replace(" ", "")
    canonical = {
        "N/C": "N/C",
        "S/C": "S/C",
        "P/C": "P/C",
        "O/C": "O/C",
        "H/C": "H/C",
        "DBE-O": "DBE-O",
        "DBE/C": "DBE/C",
        "DBE/H": "DBE/H",
        "DBE/O": "DBE/O",
        "AImod": "AImod",
        "NOSC": "NOSC",
        "is_CRAM": "CRAM",
        "isCRAM": "CRAM",
        "neutral_mass": "Neutral mass",
        "neutral_mass_rounded": "Rounded neutral mass",
        "PeakHeight": "Peak Height",
        "Peak_Height": "Peak Height",
    }
    if text in canonical:
        return canonical[text]
    if compact in canonical:
        return canonical[compact]
    ascii_compact = re.sub(r"[^A-Za-z0-9]+", "", text)
    fuzzy = {
        "HC": "H/C",
        "OC": "O/C",
        "NC": "N/C",
        "SC": "S/C",
        "PC": "P/C",
        "DBEO": "DBE-O",
        "DBEC": "DBE/C",
        "DBEH": "DBE/H",
        "DBEO2": "DBE/O",
    }
    if ascii_compact in fuzzy:
        return fuzzy[ascii_compact]
    safe = re.sub(r"[^A-Za-z0-9_./+\-() ]+", "", text).strip()
    return safe or "Feature"


def _deduplicate_feature_labels(labels: list[str]) -> list[str]:
    used = {}
    result = []
    for label in labels:
        base = _clean_feature_label(label)
        count = used.get(base, 0)
        used[base] = count + 1
        result.append(base if count == 0 else f"{base}_{count + 1}")
    return result


def _resolve_dpr_csv(task: Task) -> str | None:
    candidates = []
    if task.csv_path:
        candidates.append(Path(task.csv_path))
    final_file = (task.result or {}).get("final_file")
    if final_file and task.upload_dir:
        candidates.append(Path(task.upload_dir) / final_file)
    for path in candidates:
        if path.exists() and path.is_file():
            return str(path)
    return None


def extract_elements(formula):
    elements = {'C': 0, 'H': 0, 'O': 0, 'N': 0, 'P': 0, 'S': 0}
    if not isinstance(formula, str):
        return elements
    for element, count in re.findall(r'([A-Z][a-z]*)(\d*)', formula):
        if element in elements:
            elements[element] = int(count) if count else 1
    return elements


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


def _load_ml_deps():
    try:
        import shap
        import xgboost
        from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
        from sklearn.model_selection import GridSearchCV, train_test_split
        from sklearn.preprocessing import LabelEncoder
    except ImportError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Required packages not installed: {e}. Please install xgboost, shap, scikit-learn.",
        )
    return {
        "shap": shap,
        "xgboost": xgboost,
        "accuracy_score": accuracy_score,
        "classification_report": classification_report,
        "confusion_matrix": confusion_matrix,
        "GridSearchCV": GridSearchCV,
        "train_test_split": train_test_split,
        "LabelEncoder": LabelEncoder,
    }


def _normalize_dpr_df(df: pd.DataFrame):
    required_cols = ['MolForm', 'Col1', 'Col2', 'NewCol']
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing required columns: {missing}")
    df = df.copy()
    df = df[df['NewCol'].notna()]
    df['NewCol'] = df['NewCol'].astype(str).str.strip()
    df = df[df['NewCol'] != ""]
    return df


def _class_summary(df: pd.DataFrame):
    df = _normalize_dpr_df(df)
    counts = df['NewCol'].value_counts().sort_index()
    return [{"label": str(label), "count": int(count)} for label, count in counts.items()]


def _parse_selected_classes(value: Optional[str] = None):
    if not value:
        return None
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
    except json.JSONDecodeError:
        pass
    return [part.strip() for part in str(value).split(",") if part.strip()]


def _validate_dpr_df(df: pd.DataFrame, selected_classes: Optional[List[str]] = None):
    df = _normalize_dpr_df(df)
    if selected_classes:
        selected = [str(c).strip() for c in selected_classes if str(c).strip()]
        selected = list(dict.fromkeys(selected))
        available = set(df['NewCol'].unique())
        missing = [c for c in selected if c not in available]
        if missing:
            raise HTTPException(status_code=400, detail=f"Selected classes not found in NewCol: {missing}")
        df = df[df['NewCol'].isin(selected)]
    if df['NewCol'].nunique() < 2:
        raise HTTPException(status_code=400, detail="At least two DPR classes are required for machine learning")
    if df['NewCol'].nunique() > 3:
        raise HTTPException(status_code=400, detail="Please select two or three classes for machine learning")
    if len(df) < 6:
        raise HTTPException(status_code=400, detail="At least six rows are required for machine learning")
    class_counts = df['NewCol'].value_counts()
    too_small = class_counts[class_counts < 2]
    if not too_small.empty:
        raise HTTPException(
            status_code=400,
            detail=f"Each selected class must contain at least two rows. Too few rows: {too_small.to_dict()}",
        )
    return df


def _figure_to_outputs(fig):
    apply_font_to_figure(fig)
    png_buf = io.BytesIO()
    pdf_buf = io.BytesIO()
    fig.savefig(png_buf, format='png', dpi=150, bbox_inches='tight')
    fig.savefig(pdf_buf, format='pdf', dpi=300, bbox_inches='tight')
    plt.close(fig)
    png_buf.seek(0)
    pdf_buf.seek(0)
    return {
        "png": base64.b64encode(png_buf.getvalue()).decode('utf-8'),
        "pdf": base64.b64encode(pdf_buf.getvalue()).decode('utf-8'),
    }


def _build_shap_plot(shap, best_model, X_background, X_explain, class_index: int, class_name: str, num_classes: int, dataset_label: str):
    _configure_ml_plot_fonts()
    background = X_background
    fig = plt.figure(figsize=(11, 8))
    try:
        explainer = shap.TreeExplainer(best_model)
        shap_values = explainer(X_explain)
        values = shap_values.values
        if getattr(values, "ndim", 0) == 3:
            shap_values = shap.Explanation(
                values=values[:, :, class_index],
                base_values=shap_values.base_values[:, class_index],
                data=shap_values.data,
                feature_names=shap_values.feature_names,
            )
        elif num_classes == 2 and class_index == 0:
            shap_values = shap.Explanation(
                values=-values,
                base_values=-shap_values.base_values,
                data=shap_values.data,
                feature_names=shap_values.feature_names,
            )
        shap.plots.beeswarm(shap_values, max_display=15, show=False, color_bar_label="Feature value")
        fig = plt.gcf()
        fig.set_size_inches(11, 8)
        plt.title(f"SHAP Beeswarm for class {class_name} ({dataset_label})")
        apply_font_to_figure(fig)
        plt.subplots_adjust(left=0.34, right=0.98, bottom=0.12, top=0.92)
    except Exception:
        plt.close(fig)
        fig, ax = plt.subplots(figsize=(11, 8))
        importances = getattr(best_model, "feature_importances_", np.zeros(background.shape[1]))
        order = np.argsort(importances)[-15:]
        ax.barh(np.array(background.columns)[order], importances[order], color="#3b82f6")
        ax.set_title(f"Feature Importance for class {class_name}")
        apply_font_to_figure(fig)
        plt.subplots_adjust(left=0.34, right=0.98, bottom=0.12, top=0.92)
    return fig


def _analyze_dataframe(
    df: pd.DataFrame,
    source_name: str = "",
    selected_classes: Optional[List[str]] = None,
    shap_class: Optional[str] = None,
    shap_dataset: str = "train",
):
    deps = _load_ml_deps()
    df = _validate_dpr_df(df, selected_classes)

    element_df = pd.DataFrame([extract_elements(formula) for formula in df['MolForm']])
    element_df = element_df.loc[:, element_df.sum() != 0]
    data = pd.concat([df.reset_index(drop=True), element_df.reset_index(drop=True)], axis=1)

    if 'C' in element_df.columns:
        carbon = data['C'].replace(0, np.nan)
        if 'H' in element_df.columns:
            data['H/C'] = data['H'] / carbon
        if 'O' in element_df.columns:
            data['O/C'] = data['O'] / carbon
        if 'N' in element_df.columns:
            data['N/C'] = data['N'] / carbon
        if 'S' in element_df.columns:
            data['S/C'] = data['S'] / carbon
        if 'P' in element_df.columns:
            data['P/C'] = data['P'] / carbon

    element_cols_to_exclude = ['C', 'H', 'O', 'N', 'P', 'S']
    exclude = {'MolForm', 'Col1', 'Col2', 'NewCol', *element_cols_to_exclude}
    feature_series = {}
    feature_name_map = {}
    for idx, col in enumerate(data.columns):
        if col in exclude:
            continue
        cleaned = _clean_feature_label(col)
        if cleaned in feature_series:
            continue
        feature_series[cleaned] = pd.to_numeric(data.iloc[:, idx], errors='coerce')
        feature_name_map[str(col)] = cleaned
    X = pd.DataFrame(feature_series).fillna(0)
    if X.empty:
        raise HTTPException(status_code=400, detail="No numeric feature columns available for machine learning")
    plot_feature_cols = list(X.columns)

    label_encoder = deps["LabelEncoder"]()
    y_encoded = label_encoder.fit_transform(data['NewCol'])
    stratify = y_encoded
    num_classes = len(label_encoder.classes_)
    n_rows = len(X)
    test_count = max(num_classes, int(math.ceil(n_rows * 0.2)))
    train_count = n_rows - test_count
    if train_count < num_classes:
        raise HTTPException(
            status_code=400,
            detail="Not enough rows to keep every class in both training and test sets",
        )
    test_size = test_count / n_rows

    X_train, X_test, y_train, y_test = deps["train_test_split"](
        X, y_encoded, test_size=test_size, random_state=42, stratify=stratify
    )

    model_kwargs = {
        "random_state": 42,
        "eval_metric": "mlogloss" if num_classes > 2 else "logloss",
    }
    if num_classes > 2:
        model_kwargs.update({"objective": "multi:softprob", "num_class": num_classes})
    else:
        model_kwargs.update({"objective": "binary:logistic"})
    xgb_classifier = deps["xgboost"].XGBClassifier(**model_kwargs)

    param_grid = {
        "max_depth": [3, 5, 7],
        "learning_rate": [0.1, 0.2],
        "n_estimators": [100, 200],
        "gamma": [0, 0.1],
        "subsample": [0.8, 1.0],
        "colsample_bytree": [0.8, 1.0],
    }
    train_class_counts = np.bincount(y_train, minlength=num_classes)
    cv_folds = min(5, int(train_class_counts.min()))
    if cv_folds < 2:
        raise HTTPException(
            status_code=400,
            detail="Not enough training rows per class for cross-validation grid search",
        )
    candidate_count = int(np.prod([len(values) for values in param_grid.values()]))
    grid_search = deps["GridSearchCV"](
        estimator=xgb_classifier,
        param_grid=param_grid,
        cv=cv_folds,
        scoring="accuracy",
        n_jobs=-1,
        verbose=0,
    )
    fit_start = time.perf_counter()
    grid_search.fit(X_train, y_train)
    fit_seconds = round(time.perf_counter() - fit_start, 4)
    best_model = grid_search.best_estimator_
    best_params = {str(key): value for key, value in grid_search.best_params_.items()}
    best_cv_score = round(float(grid_search.best_score_), 4)

    y_pred = best_model.predict(X_test)
    y_pred_train = best_model.predict(X_train)
    accuracy = deps["accuracy_score"](y_test, y_pred)
    accuracy_train = deps["accuracy_score"](y_train, y_pred_train)

    labels = list(range(num_classes))
    class_names = [str(c) for c in label_encoder.classes_]
    shap_target_class = str(shap_class).strip() if shap_class else class_names[-1]
    if shap_target_class not in class_names:
        shap_target_class = class_names[-1]
    shap_target_index = class_names.index(shap_target_class)
    shap_dataset = (shap_dataset or "train").strip().lower()
    shap_dataset_map = {
        "train": ("Train set", "Train set", X_train),
        "test": ("Test set", "Test set", X_test),
        "all": ("All data", "All data", X),
    }
    shap_dataset_key = shap_dataset if shap_dataset in shap_dataset_map else "train"
    shap_dataset_label, shap_dataset_plot_label, X_shap = shap_dataset_map[shap_dataset_key]
    report_test = deps["classification_report"](
        y_test, y_pred, labels=labels, target_names=class_names, zero_division=0
    )
    report_train = deps["classification_report"](
        y_train, y_pred_train, labels=labels, target_names=class_names, zero_division=0
    )
    conf_matrix_test = deps["confusion_matrix"](y_test, y_pred, labels=labels)
    conf_matrix_train = deps["confusion_matrix"](y_train, y_pred_train, labels=labels)

    plots = {}
    plot_pdfs = {}
    _configure_ml_plot_fonts()
    fig_corr, ax_corr = plt.subplots(figsize=(12, 10))
    sns.heatmap(X.corr(), annot=False, cmap='coolwarm', fmt=".2f", linewidths=0.5, ax=ax_corr)
    ax_corr.set_title("Feature Correlation Matrix", fontsize=14)
    plt.tight_layout()
    corr_outputs = _figure_to_outputs(fig_corr)
    plots['correlation'] = corr_outputs["png"]
    plot_pdfs['correlation'] = corr_outputs["pdf"]

    fig_conf, ax_conf = plt.subplots(figsize=(8, 6))
    sns.heatmap(conf_matrix_test, annot=True, fmt="d", cmap="Blues",
                xticklabels=class_names, yticklabels=class_names, ax=ax_conf)
    ax_conf.set_xlabel("Predicted", fontsize=12)
    ax_conf.set_ylabel("Actual", fontsize=12)
    ax_conf.set_title("Confusion Matrix (Test Set)", fontsize=14)
    plt.tight_layout()
    conf_outputs = _figure_to_outputs(fig_conf)
    plots['confusion'] = conf_outputs["png"]
    plot_pdfs['confusion'] = conf_outputs["pdf"]

    shap_start = time.perf_counter()
    shap_outputs = _figure_to_outputs(_build_shap_plot(
        deps["shap"], best_model, X_train, X_shap, shap_target_index, shap_target_class, num_classes, shap_dataset_plot_label
    ))
    shap_seconds = round(time.perf_counter() - shap_start, 4)
    plots['shap'] = shap_outputs["png"]
    plot_pdfs['shap'] = shap_outputs["pdf"]

    return {
        "source_name": source_name,
        "row_count": int(len(df)),
        "label_mapping": {str(k): int(v) for k, v in zip(label_encoder.classes_, range(num_classes))},
        "selected_classes": class_names,
        "shap_target_class": shap_target_class,
        "shap_target_index": shap_target_index,
        "shap_dataset": shap_dataset_key,
        "shap_dataset_label": shap_dataset_label,
        "train_row_count": int(len(X_train)),
        "test_row_count": int(len(X_test)),
        "shap_row_count": int(len(X_shap)),
        "model_fit_seconds": fit_seconds,
        "shap_seconds": shap_seconds,
        "grid_search_cv": int(cv_folds),
        "grid_search_candidates": int(candidate_count),
        "best_cv_score": best_cv_score,
        "accuracy_test": round(float(accuracy), 4),
        "accuracy_train": round(float(accuracy_train), 4),
        "best_params": best_params,
        "report_test": report_test,
        "report_train": report_train,
        "confusion_matrix_test": conf_matrix_test.tolist(),
        "confusion_matrix_train": conf_matrix_train.tolist(),
        "feature_columns": plot_feature_cols,
        "feature_name_map": feature_name_map,
        "plots": plots,
        "plot_pdfs": plot_pdfs,
    }


@router.get("/dpr-files")
def list_dpr_files(db: Session = Depends(get_db)):
    tasks = (
        db.query(Task)
        .filter(Task.task_type == "dpr", Task.status == "success")
        .order_by(Task.created_at.desc())
        .all()
    )
    files = []
    for t in tasks:
        csv_path = _resolve_dpr_csv(t)
        if not csv_path:
            continue
        classes = []
        try:
            classes = _class_summary(_read_csv_auto(csv_path))
        except Exception:
            classes = []
        files.append({
            "id": t.id,
            "filename": t.filename,
            "final_file": (t.result or {}).get("final_file"),
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "row_count": (t.result or {}).get("binary_matrix_shape", [None])[0],
            "classes": classes,
        })
    return {"files": files}


@router.post("/inspect")
async def inspect_ml_file(file: UploadFile = File(...), db: Session = Depends(get_db)):
    try:
        await file.seek(0)
        df = _read_csv_auto(file.file)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read CSV: {str(e)}")
    return {"source_name": file.filename or "uploaded.csv", "classes": _class_summary(df)}


@router.get("/inspect-task/{task_id}")
def inspect_ml_task(task_id: str, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.task_type != "dpr" or task.status != "success":
        raise HTTPException(status_code=400, detail="Only successful DPR data-analysis tasks can be used")
    csv_path = _resolve_dpr_csv(task)
    if not csv_path:
        raise HTTPException(status_code=404, detail="DPR result CSV not found")
    try:
        df = _read_csv_auto(csv_path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read DPR CSV: {str(e)}")
    return {"source_name": task.filename, "classes": _class_summary(df)}


@router.post("/analyze")
async def run_ml_analysis(
    file: UploadFile = File(...),
    selected_classes: Optional[str] = Form(None),
    shap_class: Optional[str] = Form(None),
    shap_dataset: str = Form("train"),
    db: Session = Depends(get_db),
):
    try:
        await file.seek(0)
        df = _read_csv_auto(file.file)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read CSV: {str(e)}")
    return _analyze_dataframe(
        df,
        source_name=file.filename or "uploaded.csv",
        selected_classes=_parse_selected_classes(selected_classes),
        shap_class=shap_class,
        shap_dataset=shap_dataset,
    )


@router.post("/analyze-task/{task_id}")
def run_ml_analysis_from_task(
    task_id: str,
    selected_classes: Optional[str] = Form(None),
    shap_class: Optional[str] = Form(None),
    shap_dataset: str = Form("train"),
    db: Session = Depends(get_db),
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.task_type != "dpr" or task.status != "success":
        raise HTTPException(status_code=400, detail="Only successful DPR data-analysis tasks can be used")
    csv_path = _resolve_dpr_csv(task)
    if not csv_path:
        raise HTTPException(status_code=404, detail="DPR result CSV not found")
    try:
        df = _read_csv_auto(csv_path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read DPR CSV: {str(e)}")
    return _analyze_dataframe(
        df,
        source_name=task.filename,
        selected_classes=_parse_selected_classes(selected_classes),
        shap_class=shap_class,
        shap_dataset=shap_dataset,
    )


@router.get("/download-report/{task_id}")
def download_ml_report(task_id: str, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if not task.result or 'ml_analysis' not in task.result:
        raise HTTPException(status_code=400, detail="No ML analysis results available")
    return task.result['ml_analysis']
