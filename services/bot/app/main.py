#genai: DocSeva bot entrypoint — clears proxy vars, starts polling.
from __future__ import annotations

import logging
import os

# Clear any proxy vars injected by the host environment
for _var in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"):
    os.environ.pop(_var, None)

from app.config import settings
from app.bot import build_app

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    logger.info("Starting DocSeva bot (env=%s)", settings.environment)
    app = build_app()
    app.run_polling(
        allowed_updates=["message", "callback_query"],
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()
