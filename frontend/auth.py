"""Streamlit session helpers for password-based auth."""
from __future__ import annotations

import streamlit as st

from frontend import api_client


def current_user() -> dict | None:
    token = st.session_state.get("session_token")
    if not token:
        return None
    user = st.session_state.get("user")
    if user is None:
        user = api_client.get_me(token)
        if user is None:
            logout()
            return None
        st.session_state["user"] = user
    return user


def logout() -> None:
    for key in ("session_token", "user"):
        st.session_state.pop(key, None)


def _auth_forms() -> None:
    tab1, tab2 = st.tabs(["Sign in", "Register"])

    with tab1:
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")
        if st.button("Sign in", type="primary", key="login_btn"):
            if not email or not password:
                st.warning("Please enter your email and password.")
            else:
                try:
                    result = api_client.login(email.strip(), password)
                    st.session_state["session_token"] = result["session_token"]
                    st.session_state["user"] = result["user"]
                    st.rerun()
                except Exception as e:
                    msg = str(e)
                    if "401" in msg:
                        st.error("Incorrect email or password.")
                    else:
                        st.error("Sign in failed. Please try again.")

    with tab2:
        st.caption("First time? Create your account below.")
        r_name = st.text_input("Display name", key="reg_name")
        r_email = st.text_input("Email", key="reg_email")
        r_pw = st.text_input("Password (min 8 characters)", type="password", key="reg_pw")
        if st.button("Create account", type="primary", key="reg_btn"):
            if not r_name or not r_email or not r_pw:
                st.warning("Please fill in all fields.")
            elif len(r_pw) < 8:
                st.warning("Password must be at least 8 characters.")
            else:
                try:
                    result = api_client.register(r_email.strip(), r_pw, r_name.strip())
                    st.session_state["session_token"] = result["session_token"]
                    st.session_state["user"] = result["user"]
                    st.rerun()
                except Exception as e:
                    msg = str(e)
                    if "403" in msg:
                        st.error("Your email isn't on the invite list.")
                    elif "409" in msg:
                        st.error("An account with that email already exists.")
                    else:
                        st.error("Registration failed. Please try again.")


def require_login() -> dict:
    """Return the logged-in user, or render the auth forms and stop the page."""
    user = current_user()
    if user is None:
        _auth_forms()
        st.stop()
    return user
