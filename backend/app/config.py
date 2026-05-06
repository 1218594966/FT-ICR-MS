import os
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "FT-ICR MS Web Platform"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    UPLOAD_DIR: Path = BASE_DIR / "uploads"
    RESULT_DIR: Path = BASE_DIR / "results"
    LOCAL_DB_DIR: Path = BASE_DIR / "local_db"
    REF_DIR: Path = BASE_DIR / "ref"

    DATABASE_URL: str = f"sqlite:///{(BASE_DIR / 'fticrms.db').as_posix()}"
    MAX_UPLOAD_SIZE: int = 500 * 1024 * 1024  # 500MB

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()

settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
settings.RESULT_DIR.mkdir(parents=True, exist_ok=True)


def get_default_params() -> dict:
    return {
        "peak_detection": {
            "threshold_method": "log",
            "noise_threshold_log_nsigma": 6,
            "peak_min_prominence_percent": 0.01,
        },
        "kendrick_filter": {
            "kendrick_rounding_method": "ceil",
        },
        "calibration": {
            "min_noise_mz": 100,
            "max_noise_mz": 999,
            "min_picking_mz": 100,
            "max_picking_mz": 999,
            "max_calib_ppm_error": 1,
            "min_calib_ppm_error": -1,
            "calib_pol_order": 2,
        },
        "preliminary_search": {
            "used_atoms": {"C": [4, 50], "H": [4, 120], "O": [1, 50]},
            "min_ppm_error": -5,
            "max_ppm_error": 5,
            "is_protonated": True,
            "is_radical": False,
            "is_adduct": True,
        },
        "full_search": {
            "used_atoms": {
                "C": [4, 50],
                "H": [4, 120],
                "O": [1, 50],
                "N": [0, 5],
                "S": [0, 3],
                "P": [0, 0],
                "Cl": [0, 0],
            },
            "min_ppm_error": -1,
            "max_ppm_error": 1,
            "is_protonated": True,
            "is_radical": False,
            "is_adduct": False,
            "min_hc": 0.3,
            "max_hc": 2.25,
            "min_oc": 0.0,
            "max_oc": 1.2,
        },
    }
