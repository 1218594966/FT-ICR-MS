import base64
import io
import json
import os
import re
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
    configure_matplotlib_fonts("Times New Roman", pdf_fonttype=3)


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
        from sklearn.model_selection import train_test_split
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
    return df


def _figure_to_base64(fig):
    buf = io.BytesIO()
    apply_font_to_figure(fig)
    fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.getvalue()).decode('utf-8')


def _build_shap_plot(shap, best_model, X_background, X_explain, class_index: int, class_name: str, num_classes: int, dataset_label: str):
    _configure_ml_plot_fonts()
    max_shap_rows = 500
    if len(X_explain) > max_shap_rows:
        X_explain = X_explain.sample(n=max_shap_rows, random_state=42)
    background = X_background
    if len(background) > max_shap_rows:
        background = background.sample(n=max_shap_rows, random_state=42)
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
        shap.plots.beeswarm(shap_values, max_display=15, show=False)
        plt.title(f"SHAP Beeswarm for class {class_name} ({dataset_label})")
        apply_font_to_figure(plt.gcf())
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

    if 'N' in element_df.columns and 'C' in element_df.columns:
        data['N/C'] = data['N'] / data['C'].replace(0, 1)
    if 'S' in element_df.columns and 'C' in element_df.columns:
        data['S/C'] = data['S'] / data['C'].replace(0, 1)

    element_cols_to_exclude = ['C', 'H', 'O', 'N', 'P', 'S']
    exclude = ['MolForm', 'Col1', 'Col2', 'NewCol'] + element_cols_to_exclude
    feature_cols = [col for col in data.columns if col not in exclude]
    X = data[feature_cols].apply(pd.to_numeric, errors='coerce').fillna(0)
    if X.empty:
        raise HTTPException(status_code=400, detail="No numeric feature columns available for machine learning")

    label_encoder = deps["LabelEncoder"]()
    y_encoded = label_encoder.fit_transform(data['NewCol'])
    class_counts = pd.Series(y_encoded).value_counts()
    min_class_count = int(class_counts.min())
    stratify = y_encoded if min_class_count >= 2 else None

    X_train, X_test, y_train, y_test = deps["train_test_split"](
        X, y_encoded, test_size=0.2, random_state=42, stratify=stratify
    )

    num_classes = len(label_encoder.classes_)
    model_kwargs = {
        "random_state": 42,
        "eval_metric": "mlogloss" if num_classes > 2 else "logloss",
        "n_jobs": 2,
        "max_depth": 3,
        "learning_rate": 0.08,
        "n_estimators": 120,
        "subsample": 0.9,
        "colsample_bytree": 0.9,
    }
    if num_classes > 2:
        model_kwargs.update({"objective": "multi:softprob", "num_class": num_classes})
    else:
        model_kwargs.update({"objective": "binary:logistic"})
    xgb_classifier = deps["xgboost"].XGBClassifier(**model_kwargs)

    best_model = xgb_classifier
    best_model.fit(X_train, y_train)
    best_params = {
        "max_depth": best_model.max_depth,
        "learning_rate": best_model.learning_rate,
        "n_estimators": best_model.n_estimators,
        "subsample": best_model.subsample,
        "colsample_bytree": best_model.colsample_bytree,
    }

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
    _configure_ml_plot_fonts()
    fig_corr, ax_corr = plt.subplots(figsize=(12, 10))
    sns.heatmap(X.corr(), annot=False, cmap='coolwarm', fmt=".2f", linewidths=0.5, ax=ax_corr)
    ax_corr.set_title("Feature Correlation Matrix", fontsize=14)
    plt.tight_layout()
    plots['correlation'] = _figure_to_base64(fig_corr)

    fig_conf, ax_conf = plt.subplots(figsize=(8, 6))
    sns.heatmap(conf_matrix_test, annot=True, fmt="d", cmap="Blues",
                xticklabels=class_names, yticklabels=class_names, ax=ax_conf)
    ax_conf.set_xlabel("Predicted", fontsize=12)
    ax_conf.set_ylabel("Actual", fontsize=12)
    ax_conf.set_title("Confusion Matrix (Test Set)", fontsize=14)
    plt.tight_layout()
    plots['confusion'] = _figure_to_base64(fig_conf)

    plots['shap'] = _figure_to_base64(_build_shap_plot(
        deps["shap"], best_model, X_train, X_shap, shap_target_index, shap_target_class, num_classes, shap_dataset_plot_label
    ))

    return {
        "source_name": source_name,
        "row_count": int(len(df)),
        "label_mapping": {str(k): int(v) for k, v in zip(label_encoder.classes_, range(num_classes))},
        "selected_classes": class_names,
        "shap_target_class": shap_target_class,
        "shap_target_index": shap_target_index,
        "shap_dataset": shap_dataset_key,
        "shap_dataset_label": shap_dataset_label,
        "shap_row_count": int(len(X_shap)),
        "accuracy_test": round(float(accuracy), 4),
        "accuracy_train": round(float(accuracy_train), 4),
        "best_params": best_params,
        "report_test": report_test,
        "report_train": report_train,
        "confusion_matrix_test": conf_matrix_test.tolist(),
        "confusion_matrix_train": conf_matrix_train.tolist(),
        "feature_columns": feature_cols,
        "plots": plots,
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
        content = await file.read()
        df = _read_csv_auto(io.BytesIO(content))
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
        content = await file.read()
        df = _read_csv_auto(io.BytesIO(content))
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
