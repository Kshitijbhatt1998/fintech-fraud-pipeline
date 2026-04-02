"""
Session-level rate limiting for the Streamlit dashboard.

Because Streamlit has no traditional HTTP API layer, rate limiting is
implemented at the session-state level:
  - Track per-user action counts + timestamps in st.session_state
  - Block expensive operations if limits are exceeded
  - Reset counters after the window expires

For a REST API layer (FastAPI), use `slowapi` instead:
  https://github.com/laurentS/slowapi

Usage:
    from src.rate_limit import check_rate_limit

    if not check_rate_limit('export', max_calls=5, window_seconds=60):
        st.warning('Too many export requests. Wait a minute and try again.')
        st.stop()
"""

import time
import logging

import streamlit as st

log = logging.getLogger(__name__)


def check_rate_limit(
    action: str,
    max_calls: int = 10,
    window_seconds: int = 60,
) -> bool:
    """Check whether the current session is within the allowed rate for `action`.

    Args:
        action:         Unique name for the action being rate-limited.
        max_calls:      Maximum number of calls allowed in the window.
        window_seconds: Rolling window size in seconds.

    Returns:
        True if the request is allowed, False if the limit is exceeded.
    """
    key = f'_rl_{action}'
    now = time.time()

    if key not in st.session_state:
        st.session_state[key] = []

    # Drop timestamps outside the current window
    window = [t for t in st.session_state[key] if now - t < window_seconds]

    if len(window) >= max_calls:
        oldest = window[0]
        retry_in = int(window_seconds - (now - oldest)) + 1
        log.warning('Rate limit hit | action=%s calls=%d window=%ds retry_in=%ds',
                    action, len(window), window_seconds, retry_in)
        return False

    window.append(now)
    st.session_state[key] = window
    return True
