"""File logging for post-mortem diagnosis.

Console output stays deliberately plain (the bot is watched live during the
12:30 drop); this logger captures the detail needed to reconstruct *why*
something failed afterwards. It writes to ``logs/bot-YYYYMMDD.log`` and never
propagates to the root logger, so nothing leaks onto the console.
"""

import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Taipei")
LOG_DIR = Path(__file__).parent.parent / "logs"


def get_logger() -> logging.Logger:
    """Return the shared file logger, configuring it on first use.

    Returns:
        A ``logging.Logger`` writing to ``logs/bot-{today}.log``.
    """
    logger = logging.getLogger("rayyatreats")
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)
    logger.propagate = False  # keep diagnostics out of the console

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    date = datetime.now(TZ).strftime("%Y%m%d")
    handler = logging.FileHandler(LOG_DIR / f"bot-{date}.log", encoding="utf-8")
    handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    )
    logger.addHandler(handler)
    return logger
