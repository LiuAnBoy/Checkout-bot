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

# Error-code registry. Each failure surfaces a short code on the console and
# tags the matching detailed entry in the log file, so the two can be matched
# by searching the code:
#   E01  商品清單整體更新失敗（抓取丟例外）
#   E02  抓不到任何商品，改用備用清單
#   E03  單一商品資料抓取出錯（例外）
#   E04  單一商品抓不到規格資料（回應為空）
#   E05  某商品搶購達最大嘗試次數仍未成功
#   E06  搶購結束時仍有商品加入失敗


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


def log_file() -> str:
    """Return the active log file as a short, user-facing path.

    Returns:
        e.g. ``"logs/bot-20260529.log"`` — suitable for pointing the user to it
        in console messages.
    """
    for handler in get_logger().handlers:
        if isinstance(handler, logging.FileHandler):
            return f"logs/{Path(handler.baseFilename).name}"
    return "logs/"


def err_hint(code: str) -> str:
    """Build the console suffix that points the user to the log for an error.

    Args:
        code: An error code from the registry above (e.g. ``"E01"``).

    Returns:
        e.g. ``"（錯誤代碼 E01，詳見 logs/bot-20260529.log）"``.
    """
    return f"（錯誤代碼 {code}，詳見 {log_file()}）"
