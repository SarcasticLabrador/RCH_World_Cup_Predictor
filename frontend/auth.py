"""Streamlit session helpers, reused by every page added in later phases.

Usage in a page:
    from frontend.auth import require_login
    user = require_login()   # halts the page with a login form if not signed in
"""
from __future__ import annotations

import streamlit as st

from frontend import api_client


def _restore_from_query_token() -> None:
    """If the URL carries a magic-link ?token=, exchange it for a session."""
    token = st.query_params.get("token")
    if not token or st.session_state.get("session_token"):
        return

    result = api_client.verify(token)
    # Clear the token from the URL either way so it isn't reused/shared.
    st.query_params.clear()
    if result:
        st.session_state["session_token"] = result["session_token"]
        st.session_state["user"] = result["user"]
        st.rerun()
    else:
        st.session_state["login_error"] = "That sign-in link is invalid or has expired."


def current_user() -> dict | None:
    _restore_from_query_token()
    token = st.session_state.get("session_token")
    if not token:
        return None
    user = st.session_state.get("user")
    if user is None:
        user = api_client.get_me(token)
        if user is None:  # session expired/revoked
            logout()
            return None
        st.session_state["user"] = user
    return user


def logout() -> None:
    for key in ("session_token", "user"):
        st.session_state.pop(key, None)


def _login_form() -> None:
    st.subheader("Sign in")
    st.caption("Enter your work email and we'll send you a one-time sign-in link.")
    if err := st.session_state.pop("login_error", None):
        st.error(err)

    email = st.text_input("Email", key="login_email")
    if st.button("Send me a sign-in link", type="primary"):
        if not email or "@" not in email:
            st.warning("Please enter a valid email address.")
        else:
            try:
                resp = api_client.request_link(email.strip())
                st.success(resp.get("message", "Check your inbox."))
            except Exception:
                st.error("Something went wrong sending the link. Please try again.")


def require_login() -> dict:
    """Return the logged-in user, or render the login form and stop the page."""
    user = current_user()
    if user is None:
        _login_form()
        st.stop()
    return user
