import os
import sys
import json
import time
import zipfile
import shutil
import traceback
from pathlib import Path
from typing import Callable, Optional
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


@dataclass
class PipelineContext:
    file_path: str = ""
    mass_spectrum = None
    mso_df: Optional[pd.DataFrame] = None
    ref_file: str = ""
    db_url: str = ""
    params: dict = field(default_factory=dict)
    step_results: dict = field(default_factory=dict)
    timings: dict = field(default_factory=dict)
    error: Optional[str] = None


def extract_upload(upload_path: str, extract_dir: str) -> str:
    p = Path(upload_path)
    if p.suffix.lower() == ".zip":
        with zipfile.ZipFile(p, "r") as zf:
            extract_root = Path(extract_dir).resolve()
            for member in zf.infolist():
                dest = (extract_root / member.filename.replace("\\", "/").lstrip("/")).resolve()
                if extract_root != dest and extract_root not in dest.parents:
                    raise ValueError("Invalid ZIP file path")
                if member.is_dir():
                    dest.mkdir(parents=True, exist_ok=True)
                    continue
                dest.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(member) as src, open(dest, "wb") as out:
                    shutil.copyfileobj(src, out)
        extracted = list(Path(extract_dir).iterdir())
        d_dirs = [d for d in extracted if d.is_dir() and d.suffix.lower() == ".d"]
        if d_dirs:
            return str(d_dirs[0])
        if len(extracted) == 1 and extracted[0].is_dir():
            return str(extracted[0])
        return extract_dir
    return upload_path


def step1_peak_detection(ctx: PipelineContext, progress_cb: Optional[Callable] = None) -> dict:
    from local_corems.transient.input.brukerSolarix import ReadBrukerSolarix
    from local_corems.encapsulation.factory.parameters import MSParameters

    if progress_cb:
        progress_cb(1, "原始数据读取与峰检测", 0)

    p = ctx.params.get("peak_detection", {})
    MSParameters.ms_peak.kendrick_rounding_method = ctx.params.get(
        "kendrick_filter", {}
    ).get("kendrick_rounding_method", "ceil")
    MSParameters.mass_spectrum.threshold_method = p.get("threshold_method", "log")
    MSParameters.mass_spectrum.noise_threshold_log_nsigma = p.get(
        "noise_threshold_log_nsigma", 6
    )
    MSParameters.ms_peak.peak_min_prominence_percent = p.get(
        "peak_min_prominence_percent", 0.01
    )

    if progress_cb:
        progress_cb(1, "原始数据读取与峰检测", 30)

    bruker_reader = ReadBrukerSolarix(ctx.file_path)
    mass_spectrum = bruker_reader.get_transient().get_mass_spectrum(
        plot_result=False, auto_process=True
    )
    ctx.mass_spectrum = mass_spectrum
    total_peaks = len(mass_spectrum)

    mz_arr = np.array(mass_spectrum.mz_exp).tolist()
    abund_arr = np.array(mass_spectrum.abundance).tolist()

    if progress_cb:
        progress_cb(1, "原始数据读取与峰检测", 100)

    return {
        "total_peaks": total_peaks,
        "mz": mz_arr,
        "abundance": abund_arr,
    }


def step2_kendrick_filter(ctx: PipelineContext, progress_cb: Optional[Callable] = None) -> dict:
    if progress_cb:
        progress_cb(2, "Kendrick 质量噪声过滤", 0)

    ms = ctx.mass_spectrum
    km = ms.kendrick_mass
    kmd = ms.kmd

    lower = 0.0011232 * km + 0.05
    upper = 0.0011232 * km + 0.2
    llimit = kmd <= lower
    ulimit = kmd >= upper
    noiseWindow = (llimit + ulimit) != True
    noise_count = int(np.sum(noiseWindow))

    if progress_cb:
        progress_cb(2, "Kendrick 质量噪声过滤", 50)

    if noise_count >= 100:
        nnPercentile = np.percentile(ms.abundance[noiseWindow], q=99)
        plimit = ms.abundance < nnPercentile
        filterIndex = np.where(plimit & noiseWindow)[0]
        ms.filter_by_index(filterIndex)

    filtered_peaks = len(ms.mz_exp)

    if progress_cb:
        progress_cb(2, "Kendrick 质量噪声过滤", 100)

    return {
        "noise_window_peaks": noise_count,
        "filtered_peaks": filtered_peaks,
    }


def step3_preliminary_search(ctx: PipelineContext, progress_cb: Optional[Callable] = None) -> dict:
    from local_corems.molecular_id.search.molecularFormulaSearch import SearchMolecularFormulas
    from local_corems.encapsulation.factory.parameters import MSParameters

    if progress_cb:
        progress_cb(3, "初步分子式搜索", 0)

    ms = ctx.mass_spectrum
    p = ctx.params.get("preliminary_search", {})

    ms.molecular_search_settings.url_database = ctx.db_url
    atoms = p.get("used_atoms", {"C": [4, 50], "H": [4, 120], "O": [1, 50]})
    for elem, rng in atoms.items():
        ms.molecular_search_settings.usedAtoms[elem] = tuple(rng)
    ms.molecular_search_settings.min_ppm_error = p.get("min_ppm_error", -5)
    ms.molecular_search_settings.max_ppm_error = p.get("max_ppm_error", 5)
    ms.molecular_search_settings.isProtonated = p.get("is_protonated", True)
    ms.molecular_search_settings.isRadical = p.get("is_radical", False)
    ms.molecular_search_settings.isadduct = p.get("is_adduct", True)
    MSParameters.molecular_search.use_min_peaks_filter = False

    if progress_cb:
        progress_cb(3, "初步分子式搜索", 40)

    SearchMolecularFormulas(ms, first_hit=True).run_worker_mass_spectrum()

    if progress_cb:
        progress_cb(3, "初步分子式搜索", 80)

    msoDf = ms.to_dataframe()
    mz_arr = np.array(msoDf["m/z"]).tolist()
    ppm_arr = np.array(msoDf["m/z Error (ppm)"]).tolist()
    formula_arr = msoDf["Molecular Formula"].fillna("").tolist()

    if progress_cb:
        progress_cb(3, "初步分子式搜索", 100)

    return {
        "status": "completed",
        "mz": mz_arr,
        "ppm_error": ppm_arr,
        "formulas": formula_arr,
    }


def step4_calibration(ctx: PipelineContext, progress_cb: Optional[Callable] = None) -> dict:
    from local_corems.transient.input.brukerSolarix import ReadBrukerSolarix
    from local_corems.mass_spectrum.calc.Calibration import MzDomainCalibration
    from local_corems.encapsulation.factory.parameters import MSParameters

    if progress_cb:
        progress_cb(4, "内部质量校准", 0)

    p = ctx.params.get("calibration", {})
    ref_file = ctx.ref_file

    MSParameters.mass_spectrum.min_noise_mz = p.get("min_noise_mz", 100)
    MSParameters.mass_spectrum.max_noise_mz = p.get("max_noise_mz", 999)
    MSParameters.mass_spectrum.min_picking_mz = p.get("min_picking_mz", 100)
    MSParameters.mass_spectrum.max_picking_mz = p.get("max_picking_mz", 999)

    if progress_cb:
        progress_cb(4, "内部质量校准", 30)

    bruker_reader = ReadBrukerSolarix(ctx.file_path)
    mass_spectrum = bruker_reader.get_transient().get_mass_spectrum(
        plot_result=False, auto_process=True
    )
    mass_spectrum.settings.max_calib_ppm_error = p.get("max_calib_ppm_error", 2)
    mass_spectrum.settings.min_calib_ppm_error = p.get("min_calib_ppm_error", 0)
    mass_spectrum.settings.calib_pol_order = p.get("calib_pol_order", 2)

    if progress_cb:
        progress_cb(4, "内部质量校准", 60)

    MzDomainCalibration(mass_spectrum, ref_file).run()
    ctx.mass_spectrum = mass_spectrum

    if progress_cb:
        progress_cb(4, "内部质量校准", 100)

    return {"status": "calibrated", "total_peaks": len(mass_spectrum)}


def step5_full_search(ctx: PipelineContext, progress_cb: Optional[Callable] = None) -> dict:
    from local_corems.molecular_id.search.molecularFormulaSearch import SearchMolecularFormulas

    if progress_cb:
        progress_cb(5, "完整分子式搜索", 0)

    ms = ctx.mass_spectrum
    p = ctx.params.get("full_search", {})

    ms.molecular_search_settings.url_database = ctx.db_url
    atoms = p.get("used_atoms", {})
    for elem, rng in atoms.items():
        ms.molecular_search_settings.usedAtoms[elem] = tuple(rng)

    ms.molecular_search_settings.error_method = "None"
    ms.molecular_search_settings.min_ppm_error = p.get("min_ppm_error", -1)
    ms.molecular_search_settings.max_ppm_error = p.get("max_ppm_error", 1)

    ms.settings.min_hc_filter = p.get("min_hc", 0.3)
    ms.settings.max_hc_filter = p.get("max_hc", 2.25)
    ms.settings.min_oc_filter = p.get("min_oc", 0.0)
    ms.settings.max_oc_filter = p.get("max_oc", 1.2)

    ms.molecular_search_settings.isProtonated = p.get("is_protonated", True)
    ms.molecular_search_settings.isRadical = p.get("is_radical", False)
    ms.molecular_search_settings.isadduct = p.get("is_adduct", False)

    if progress_cb:
        progress_cb(5, "完整分子式搜索", 30)

    SearchMolecularFormulas(ms, first_hit=True).run_worker_mass_spectrum()
    ms.percentile_assigned(report_error=True)

    if progress_cb:
        progress_cb(5, "完整分子式搜索", 80)

    msoDf = ms.to_dataframe()
    ctx.mso_df = msoDf

    formula_text = msoDf["Molecular Formula"].where(msoDf["Molecular Formula"].notna(), "").astype(str).str.strip()
    assigned_mask = (formula_text != "") & (~formula_text.str.lower().isin({"nan", "none", "0"}))
    assigned = int(assigned_mask.sum())
    total = len(msoDf)
    unassigned = total - assigned

    mz_arr = np.array(msoDf["m/z"]).tolist()
    ppm_arr = np.array(msoDf["m/z Error (ppm)"]).tolist()
    formula_arr = msoDf["Molecular Formula"].fillna("").tolist()

    assigned_df = msoDf[assigned_mask].copy()
    oc_arr = []
    hc_arr = []
    elem_cat_arr = []
    if not assigned_df.empty and "O/C" in assigned_df.columns and "H/C" in assigned_df.columns:
        oc_arr = np.where(np.isfinite(assigned_df["O/C"]), assigned_df["O/C"], 0).tolist()
        hc_arr = np.where(np.isfinite(assigned_df["H/C"]), assigned_df["H/C"], 0).tolist()
        for _, row in assigned_df.iterrows():
            elems = set()
            elems = set()
            for e in ["C", "H", "O", "N", "S", "P", "Cl"]:
                if e in row.index and row.get(e, 0) > 0:
                    elems.add(e)
            ELEM_CAT_MAP = {
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
            cat = ELEM_CAT_MAP.get(frozenset(elems & {'C','H','O','N','S','P','Cl'}), 'Other')
            elem_cat_arr.append(cat)

    if progress_cb:
        progress_cb(5, "完整分子式搜索", 100)

    return {
        "total_peaks": total,
        "assigned_peaks": assigned,
        "unassigned_peaks": unassigned,
        "assignment_rate": round(assigned / total * 100, 2) if total > 0 else 0,
        "mz": mz_arr,
        "ppm_error": ppm_arr,
        "formulas": formula_arr,
        "oc": oc_arr,
        "hc": hc_arr,
        "elem_category": elem_cat_arr,
    }


def step6_indices_calc(ctx: PipelineContext, progress_cb: Optional[Callable] = None) -> dict:
    if progress_cb:
        progress_cb(6, "分子指标计算", 0)

    df = ctx.mso_df
    if df is None:
        raise ValueError("No dataframe available from previous step")

    essential = ["C", "H", "O", "DBE", "Molecular Formula"]
    for col in essential:
        if col not in df.columns:
            raise ValueError(f"Missing essential column: {col}")

    for col in ["N", "P", "S", "Cl", "F"]:
        if col not in df.columns:
            df[col] = 0

    df = df.copy()
    if "Heteroatom Class" not in df.columns:
        df["Heteroatom Class"] = ""

    formula_text = df["Molecular Formula"].where(df["Molecular Formula"].notna(), "").astype(str).str.strip()
    hetero_class = df["Heteroatom Class"].where(df["Heteroatom Class"].notna(), "").astype(str).str.strip().str.lower()
    valid_formula = (formula_text != "") & (~formula_text.str.lower().isin({"nan", "none", "0"}))
    df = df[valid_formula & (hetero_class != "unassigned")].copy()
    df["Molecular Formula"] = formula_text.loc[df.index]
    df.fillna(0, inplace=True)

    if progress_cb:
        progress_cb(6, "分子指标计算", 30)

    def calc_metrics(row):
        C, H, O = row["C"], row["H"], row["O"]
        N, P, S = row["N"], row["P"], row["S"]
        Cl = row.get("Cl", 0)
        F = row.get("F", 0)
        DBE = row["DBE"]
        m = {}
        m["N/C"] = N / C if C != 0 else np.nan
        m["S/C"] = S / C if C != 0 else np.nan
        m["P/C"] = P / C if C != 0 else np.nan
        den = C - 0.5 * O - S - N - P
        m["AImod"] = (1 + C - 0.5 * O - S - 0.5 * H) / den if den != 0 else np.nan
        m["NOSC"] = -((4 * C + H - 3 * N - 2 * O + 5 * P - 2 * S - Cl - F) / C) + 4 if C != 0 else np.nan
        m["DBE-O"] = (2 * C + N + P - H + 2) / 2 - O if C != 0 else np.nan
        m["DBE/C"] = DBE / C if C != 0 else np.nan
        m["DBE/H"] = DBE / H if H != 0 else np.nan
        m["DBE/O"] = DBE / O if O != 0 else np.nan
        is_cram = 0
        if (
            0.30 <= m["DBE/C"] <= 0.68
            and 0.20 <= m["DBE/H"] <= 0.95
            and 0.77 <= m["DBE/O"] <= 1.75
        ):
            is_cram = 1
        m["is_CRAM"] = is_cram
        return pd.Series(m)

    metrics_df = df.apply(calc_metrics, axis=1)
    df = pd.concat([df, metrics_df], axis=1)

    if progress_cb:
        progress_cb(6, "分子指标计算", 70)

    df = df[(df["DBE-O"] >= -10) & (df["DBE-O"] <= 10)]
    ctx.mso_df = df

    if progress_cb:
        progress_cb(6, "分子指标计算", 100)

    return {"remaining_peaks": len(df)}


def step7_nitrogen_rule(ctx: PipelineContext, progress_cb: Optional[Callable] = None) -> dict:
    if progress_cb:
        progress_cb(7, "氮规则过滤", 0)

    df = ctx.mso_df
    atomic_masses = {
        "H": 1.00782503223, "C": 12.0, "13C": 13.00335483507,
        "N": 14.00307400443, "O": 15.99491461957, "P": 30.97376199842,
        "S": 31.9720711744, "Cl": 34.96885268,
    }

    def neutral_mass(row):
        return sum(row.get(e, 0) * m for e, m in atomic_masses.items())

    df["neutral_mass"] = df.apply(neutral_mass, axis=1)
    df.dropna(subset=["neutral_mass"], inplace=True)
    df["neutral_mass_rounded"] = df["neutral_mass"].round().astype(int)

    if progress_cb:
        progress_cb(7, "氮规则过滤", 50)

    df["is_valid"] = (
        (df["N"] == 0)
        | ((df["neutral_mass_rounded"] % 2 == 0) & (df["N"] % 2 == 0))
        | ((df["neutral_mass_rounded"] % 2 == 1) & (df["N"] % 2 == 1))
    )
    before = len(df)
    df = df[df["is_valid"]].drop(columns=["is_valid"])
    after = len(df)
    ctx.mso_df = df

    if progress_cb:
        progress_cb(7, "氮规则过滤", 100)

    return {"before": before, "after": after, "filtered": before - after}


def step8_classification(ctx: PipelineContext, progress_cb: Optional[Callable] = None) -> dict:
    if progress_cb:
        progress_cb(8, "化合物类型分类", 0)

    df = ctx.mso_df
    compounds = {
        "Lipid": ((0, 0.3), (1.5, 2.0)),
        "Peptide-like": ((0.3, 0.67), (1.5, 2.2)),
        "Carbohydrate": ((0.67, 1.2), (1.5, 2.5)),
        "Unsaturated hydrocarbon": ((0, 0.1), (0.67, 1.5)),
        "Lignin": ((0.1, 0.67), (0.67, 1.5)),
        "Condensed aromatics": ((0, 0.67), (0.3, 0.67)),
        "Tannin": ((0.67, 1.2), (0.5, 1.5)),
    }

    def classify(oc, hc):
        for name, (oc_r, hc_r) in compounds.items():
            if oc_r[0] <= oc <= oc_r[1] and hc_r[0] <= hc <= hc_r[1]:
                return name
        return "Other"

    df["Type"] = df.apply(lambda r: classify(r["O/C"], r["H/C"]), axis=1)
    ctx.mso_df = df

    type_counts = df["Type"].value_counts().to_dict()

    if progress_cb:
        progress_cb(8, "化合物类型分类", 100)

    return {"type_counts": type_counts}


def step9_weighted_avg(ctx: PipelineContext, progress_cb: Optional[Callable] = None) -> dict:
    if progress_cb:
        progress_cb(9, "加权平均指标计算", 0)

    df = ctx.mso_df
    peak_height = pd.to_numeric(df.get("Peak Height", 0), errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0).clip(lower=0)
    total_intensity = float(peak_height.sum())

    cols_to_weight = [
        "O/C", "H/C", "N/C", "S/C", "P/C", "AImod", "NOSC",
        "DBE-O", "DBE/C", "DBE/H", "DBE/O", "DBE",
    ]
    weighted = {}
    if total_intensity <= 0:
        df["RI"] = 0.0
        for col in cols_to_weight:
            if col in df.columns:
                weighted[col + "_w"] = None
        ctx.mso_df = df
        if progress_cb:
            progress_cb(9, "加权平均指标计算", 100)
        return {"weighted_averages": weighted, "total_intensity": 0.0}

    df["RI"] = peak_height / total_intensity
    for col in cols_to_weight:
        if col in df.columns:
            values = pd.to_numeric(df[col], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0)
            weighted[col + "_w"] = float((values * df["RI"]).sum())

    ctx.mso_df = df

    if progress_cb:
        progress_cb(9, "加权平均指标计算", 100)

    return {"weighted_averages": weighted, "total_intensity": total_intensity}


class AnalysisPipeline:
    def __init__(self, file_path: str, params: dict, ref_file: str, db_url: str):
        self.ctx = PipelineContext(
            file_path=file_path,
            params=params,
            ref_file=ref_file,
            db_url=db_url,
        )
        self.steps = [
            ("peak_detection", step1_peak_detection),
            ("kendrick_filter", step2_kendrick_filter),
            ("preliminary_search", step3_preliminary_search),
            ("calibration", step4_calibration),
            ("full_search", step5_full_search),
            ("indices_calc", step6_indices_calc),
            ("nitrogen_rule", step7_nitrogen_rule),
            ("classification", step8_classification),
            ("weighted_avg", step9_weighted_avg),
        ]

    def run(self, progress_cb: Optional[Callable] = None) -> dict:
        results = {}
        for step_name, step_fn in self.steps:
            t0 = time.time()
            try:
                if progress_cb:
                    progress_cb(self.steps.index((step_name, step_fn)) + 1, step_name, 0)
                result = step_fn(self.ctx, progress_cb)
                elapsed = round(time.time() - t0, 2)
                results[step_name] = {"status": "success", "data": result, "time": elapsed}
                self.ctx.timings[step_name] = elapsed
            except Exception as e:
                tb = traceback.format_exc()
                results[step_name] = {"status": "error", "error": str(e), "traceback": tb}
                self.ctx.error = str(e)
                break

        csv_path = None
        if self.ctx.mso_df is not None and self.ctx.error is None:
            csv_path = str(
                Path(self.ctx.file_path).parent / "analysis_result.csv"
            )
            self.ctx.mso_df.to_csv(csv_path, index=False)

        return {
            "steps": results,
            "csv_path": csv_path,
            "total_time": sum(self.ctx.timings.values()),
            "error": self.ctx.error,
        }
