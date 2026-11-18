"""
Settings for the browser end-to-end suite (frontend/e2e, `pnpm test:e2e`). Same as dev, but
against a dedicated database and with relaxed rate limits, because one run registers several
accounts from one IP. Rate limiting itself is covered by the backend unit tests.
"""

from .dev import *  # noqa: F403
from .dev import REST_FRAMEWORK

REST_FRAMEWORK = {
    **REST_FRAMEWORK,
    "DEFAULT_THROTTLE_RATES": dict.fromkeys(REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"], "1000/min"),
}

# The browser suite runs with payments off, so its sessions must be free.
MIN_SESSION_PRICE_CENTS = 0
