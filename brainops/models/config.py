# brainops/config/check_config.py

from pathlib import Path

from brainops.models.reconcile import CheckConfig
from brainops.utils.config import BASE_PATH, LOG_FILE_PATH


def get_check_config(scope: str = "all") -> CheckConfig:
    base = Path(BASE_PATH)
    out = Path(LOG_FILE_PATH)

    return CheckConfig(base_path=base, out_dir=out)
