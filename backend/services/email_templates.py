"""Email content builders. Kept separate so copy/styling is easy to tweak."""
from __future__ import annotations

from backend.config import get_settings


def login_email(magic_url: str, ttl_hours: int) -> tuple[str, str, str]:
    """Return (subject, html, text) for a magic-link login email."""
    app_name = get_settings().app_name
    subject = f"Your {app_name} login link"

    text = (
        f"Hi,\n\n"
        f"Use the link below to sign in to {app_name}:\n\n"
        f"{magic_url}\n\n"
        f"This link is valid for {ttl_hours} hours and can be used once.\n"
        f"If you didn't request it, you can ignore this email."
    )

    html = f"""\
<div style="font-family:system-ui,Segoe UI,Arial,sans-serif;max-width:520px;margin:auto">
  <h2 style="margin:0 0 12px">{app_name}</h2>
  <p>Click the button below to sign in:</p>
  <p style="margin:24px 0">
    <a href="{magic_url}"
       style="background:#1f6feb;color:#fff;text-decoration:none;
              padding:12px 20px;border-radius:8px;display:inline-block">
      Sign in
    </a>
  </p>
  <p style="color:#666;font-size:13px">
    This link is valid for {ttl_hours} hours and can be used once.<br>
    If you didn't request it, you can ignore this email.
  </p>
</div>"""
    return subject, html, text


def reminder_email(stage_display: str, app_url: str) -> tuple[str, str, str]:
    """Return (subject, html, text) for a 'new predictions are open' reminder."""
    app_name = get_settings().app_name
    subject = f"{app_name}: {stage_display} predictions are open"

    text = (
        f"Hi,\n\n"
        f"Predictions for the {stage_display} are now open in {app_name}.\n\n"
        f"Get your picks in before the first match kicks off:\n{app_url}\n\n"
        f"Good luck!"
    )
    html = f"""\
<div style="font-family:system-ui,Segoe UI,Arial,sans-serif;max-width:520px;margin:auto">
  <h2 style="margin:0 0 12px">{app_name}</h2>
  <p>Predictions for the <strong>{stage_display}</strong> are now open.</p>
  <p>Get your picks in before the first match kicks off.</p>
  <p style="margin:24px 0">
    <a href="{app_url}"
       style="background:#1f6feb;color:#fff;text-decoration:none;
              padding:12px 20px;border-radius:8px;display:inline-block">
      Make your predictions
    </a>
  </p>
  <p style="color:#666;font-size:13px">Good luck!</p>
</div>"""
    return subject, html, text
