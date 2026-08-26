import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)


handler = TimedRotatingFileHandler(
    LOG_DIR / "record.log",
    when="midnight",
    backupCount=5,
    encoding="utf-8",
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s]: %(message)s",
    handlers=[
        handler,
        logging.StreamHandler(),
    ],
)
logging.getLogger("httpx").setLevel(logging.CRITICAL)
logger = logging.getLogger(__name__)