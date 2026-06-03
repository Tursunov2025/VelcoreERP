"""File logging under LOG_PATH for production."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

from config.paths import LOG_PATH, ensure_data_directories


def configure_logging() -> None:
    ensure_data_directories()
    log_file = LOG_PATH / "azmus-backend.log"
    root = logging.getLogger()
    if any(isinstance(h, RotatingFileHandler) for h in root.handlers):
        return

    root.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,
        backupCount=10,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)

    if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        console = logging.StreamHandler(sys.stdout)
        console.setFormatter(fmt)
        root.addHandler(console)

    logging.getLogger("azmus.paths").info("Logging to %s", log_file)
