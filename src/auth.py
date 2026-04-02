"""
Supabase authentication gate for the Streamlit dashboard.

Authorization model:
  - Any authenticated user can read the shared fraud analytics (no user-specific rows).
  - Row-level security lives in Supabase; DuckDB is a local read-only analytics store.
  - Password reset tokens are issued by Supabase and expire per their JWT policy (default 1 h).

Environment variables:
  SUPABASE_URL       — e.g. https://YOUR-PROJECT-REF.supabase.co
  SUPABASE_ANON_KEY  — public anon key (safe to expose to browser)

Dev mode (no env vars set):
  Returns a mock user and shows a sidebar warning. Remove before production.
"""

import logging
import os
import re

import streamlit as st

log = logging.getLogger(__name__)

# ── Validation helpers ────────────────────────────────────────────────────────

_EMAIL_RE = re.compile(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$')
_MIN_PASSWORD_LEN = 8


def _validate_email(email: str) -> str | None:
    """Return error string or None if valid."""
    email = email.strip()
    if not email:
        return 'Email is required.'
    if not _EMAIL_RE.match(email):
        return 'Enter a valid email address.'
    return None


def _validate_password(password: str) -> str | None:
    """Return error string or None if valid."""
    if len(password) < _MIN_PASSWORD_LEN:
        return f'Password must be at least {_MIN_PASSWORD_LEN} characters.'
    return None


# ── Supabase client ───────────────────────────────────────────────────────────

@st.cache_resource
def _get_supabase():
    """Return a Supabase client, or None if not configured."""
    url = os.getenv('SUPABASE_URL', '').strip()
    key = os.getenv('SUPABASE_ANON_KEY', '').strip()
    if not url or not key:
        return None
    try:
        from supabase import create_client
        return create_client(url, key)
    except ImportError:
        log.warning('supabase package not installed — auth disabled')
        return None


# ── Public API ────────────────────────────────────────────────────────────────

def require_auth() -> dict:
    """Gate the page behind Supabase auth.

    Returns the authenticated user dict {'id', 'email'} or stops the app
    and renders the login form. In dev mode (no Supabase config) returns a
    mock user so the dashboard remains accessible locally.
    """
    supabase = _get_supabase()

    if supabase is None:
        st.sidebar.warning('Auth not configured — dev mode')
        return {'id': 'dev', 'email': 'dev@localhost'}

    if 'auth_user' not in st.session_state:
        _render_auth_page(supabase)
        st.stop()

    return st.session_state['auth_user']


def sign_out() -> None:
    """Sign out and clear the session."""
    supabase = _get_supabase()
    if supabase:
        try:
            supabase.auth.sign_out()
        except Exception as exc:
            log.warning('Supabase sign-out error: %s', exc)
    st.session_state.pop('auth_user', None)
    st.rerun()


# ── Auth UI ───────────────────────────────────────────────────────────────────

def _render_auth_page(supabase) -> None:
    st.title('🔍 Fraud Detection Pipeline')
    st.markdown('Sign in to access the analytics dashboard.')

    tab_in, tab_up = st.tabs(['Sign In', 'Create Account'])

    with tab_in:
        _render_signin(supabase)

    with tab_up:
        _render_signup(supabase)


def _render_signin(supabase) -> None:
    email    = st.text_input('Email', key='si_email', placeholder='you@example.com')
    password = st.text_input('Password', type='password', key='si_pass')

    if st.button('Sign In', type='primary', use_container_width=True, key='si_btn'):
        err = _validate_email(email)
        if err:
            st.error(err)
            return

        try:
            res = supabase.auth.sign_in_with_password({'email': email, 'password': password})
            st.session_state['auth_user'] = {
                'id':    res.user.id,
                'email': res.user.email,
            }
            log.info('User signed in: %s', res.user.email)
            st.rerun()
        except Exception:
            # Never expose raw exception messages to the UI (they may contain internals)
            st.error('Invalid email or password.')
            log.warning('Failed sign-in attempt for: %s', email)

    st.caption('Forgot your password? Use the link in your invitation email. '
               'Reset links expire after **1 hour** (Supabase default).')


def _render_signup(supabase) -> None:
    email     = st.text_input('Email', key='su_email', placeholder='you@example.com')
    password  = st.text_input('Password', type='password', key='su_pass')
    password2 = st.text_input('Confirm password', type='password', key='su_pass2')

    if st.button('Create Account', use_container_width=True, key='su_btn'):
        err = _validate_email(email) or _validate_password(password)
        if err:
            st.error(err)
            return
        if password != password2:
            st.error('Passwords do not match.')
            return

        try:
            supabase.auth.sign_up({'email': email, 'password': password})
            st.success('Account created — check your email to confirm before signing in.')
            log.info('New account created: %s', email)
        except Exception:
            st.error('Could not create account. The address may already be registered.')
            log.warning('Failed sign-up for: %s', email)
