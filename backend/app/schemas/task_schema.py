from pydantic import BaseModel, Field
from typing import Optional, Dict, List, Any
from datetime import datetime


class PeakDetectionParams(BaseModel):
    threshold_method: str = "log"
    noise_threshold_log_nsigma: int = 6
    peak_min_prominence_percent: float = 0.01


class KendrickFilterParams(BaseModel):
    kendrick_rounding_method: str = "ceil"


class CalibrationParams(BaseModel):
    min_noise_mz: int = 100
    max_noise_mz: int = 999
    min_picking_mz: int = 100
    max_picking_mz: int = 999
    max_calib_ppm_error: float = 2
    min_calib_ppm_error: float = 0
    calib_pol_order: int = 2


class UsedAtoms(BaseModel):
    C: List[int] = [4, 50]
    H: List[int] = [4, 120]
    O: List[int] = [1, 50]
    N: List[int] = [0, 5]
    S: List[int] = [0, 3]
    P: List[int] = [0, 0]
    Cl: List[int] = [0, 0]


class PreliminarySearchParams(BaseModel):
    used_atoms: UsedAtoms = Field(default_factory=lambda: UsedAtoms(C=[4, 50], H=[4, 120], O=[1, 50], N=[0, 0], S=[0, 0], P=[0, 0], Cl=[0, 0]))
    min_ppm_error: float = -5
    max_ppm_error: float = 5
    is_protonated: bool = True
    is_radical: bool = False
    is_adduct: bool = True


class FullSearchParams(BaseModel):
    used_atoms: UsedAtoms = Field(default_factory=UsedAtoms)
    min_ppm_error: float = -1
    max_ppm_error: float = 1
    is_protonated: bool = True
    is_radical: bool = False
    is_adduct: bool = False
    min_hc: float = 0.3
    max_hc: float = 2.25
    min_oc: float = 0.0
    max_oc: float = 1.2


class AnalysisParams(BaseModel):
    peak_detection: PeakDetectionParams = Field(default_factory=PeakDetectionParams)
    kendrick_filter: KendrickFilterParams = Field(default_factory=KendrickFilterParams)
    calibration: CalibrationParams = Field(default_factory=CalibrationParams)
    preliminary_search: PreliminarySearchParams = Field(default_factory=PreliminarySearchParams)
    full_search: FullSearchParams = Field(default_factory=FullSearchParams)


class TaskCreate(BaseModel):
    params: AnalysisParams = Field(default_factory=AnalysisParams)


class TaskResponse(BaseModel):
    id: str
    filename: str
    status: str
    current_step: str
    progress: float
    created_at: Optional[datetime]
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    error_message: Optional[str]

    class Config:
        from_attributes = True


class TaskDetailResponse(TaskResponse):
    params: Optional[dict] = None
    result: Optional[dict] = None
    csv_path: Optional[str] = None


class HistoryResponse(BaseModel):
    tasks: List[TaskResponse]
    total: int
    page: int
    page_size: int
