"""# runner.py"""

from __future__ import annotations

from brainops.utils.config import ConfigError
from brainops.utils.logger import get_logger
from brainops.utils.safe_runner import safe_main
from brainops.watcher.start import start_watcher

logger = get_logger("Brainops Watcher")


@safe_main
def main() -> None:
    """
    main _summary_

    _extended_summary_
    """
    try:
        start_watcher(logger=logger)
    except ConfigError as exc:
        # ton décorateur/infra loguera correctement ici
        if logger is not None:
            logger.error("Erreur de configuration: %s", exc)
        # à toi de décider: raise, ou exit(1) au script d'entrée


if __name__ == "__main__":
    main()
