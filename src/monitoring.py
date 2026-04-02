"""
Central monitoring setup — Sentry error tracking + structured logging.

Call setup_monitoring() once at the entry point of each script/app.
All other modules then use standard logging.getLogger(__name__).

Environment variables:
  SENTRY_DSN    — Sentry project DSN (optional; monitoring disabled if absent)
  APP_ENV       — 'development' | 'staging' | 'production' (default: development)
"""

import logging
import logging.handlers
import os
import sys
from pathlib import Path

ROOT    = Path(__file__).resolve().parent.parent
LOG_DIR = ROOT / 'logs'
LOG_DIR.mkdir(exist_ok=True)

_LOG_FORMAT = '%(asctime)s [%(levelname)s] %(name)s (%(filename)s:%(lineno)d): %(message)s'


def setup_monitoring(component: str = 'app') -> logging.Logger:
    """Initialize Sentry + rotating file + stdout logging.

    Args:
        component: Name used for the log file and Sentry transaction source.
                   E.g. 'dashboard', 'train', 'ingest'.

    Returns:
        A configured logger for the calling module.
    """
    _init_sentry(component)
    _init_logging(component)
    logger = logging.getLogger(component)

    env = os.getenv('APP_ENV', 'development')
    dsn = os.getenv('SENTRY_DSN')
    logger.info('Monitoring ready | component=%s env=%s sentry=%s',
                component, env, 'on' if dsn else 'off')
    return logger


# ── Sentry ────────────────────────────────────────────────────────────────────

def _init_sentry(component: str) -> None:
    dsn = os.getenv('SENTRY_DSN')
    if not dsn:
        return

    try:
        import sentry_sdk
        from sentry_sdk.integrations.logging import LoggingIntegration

        sentry_sdk.init(
            dsn=dsn,
            environment=os.getenv('APP_ENV', 'development'),
            release=os.getenv('APP_VERSION', 'unknown'),
            integrations=[
                LoggingIntegration(
                    level=logging.WARNING,    # breadcrumbs from WARNING+
                    event_level=logging.ERROR # events (alerts) from ERROR+
                ),
            ],
            traces_sample_rate=0.05,   # 5% of transactions — low for a data app
            send_default_pii=False,    # never send PII — critical for fintech
            server_name=component,
        )
    except ImportError:
        # sentry-sdk not installed — monitoring degrades gracefully
        pass


# ── Logging ───────────────────────────────────────────────────────────────────

def _init_logging(component: str) -> None:
    """Configure root logger: rotating file + stdout."""
    root = logging.getLogger()
    if root.handlers:
        # Already configured (e.g., called twice in the same process)
        return

    root.setLevel(logging.INFO)

    # Rotating file — 10 MB per file, keep last 5
    file_handler = logging.handlers.RotatingFileHandler(
        LOG_DIR / f'{component}.log',
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding='utf-8',
    )
    file_handler.setFormatter(logging.Formatter(_LOG_FORMAT))

    # Stdout for containers / Streamlit Cloud
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(logging.Formatter(_LOG_FORMAT))

    root.addHandler(file_handler)
    root.addHandler(stdout_handler)

    # Silence noisy third-party loggers
    for noisy in ('httpx', 'httpcore', 'urllib3', 'botocore'):
        logging.getLogger(noisy).setLevel(logging.WARNING)


# ── Helpers ───────────────────────────────────────────────────────────────────

def capture_exception(exc: Exception, context: dict | None = None) -> None:
    """Report an exception to Sentry (no-op if Sentry not configured)."""
    try:
        import sentry_sdk
        with sentry_sdk.push_scope() as scope:
            if context:
                for k, v in context.items():
                    scope.set_extra(k, v)
            sentry_sdk.capture_exception(exc)
    except ImportError:
        pass


def capture_message(message: str, level: str = 'info') -> None:
    """Send a custom Sentry message / alert."""
    try:
        import sentry_sdk
        sentry_sdk.capture_message(message, level=level)
    except ImportError:
        pass
