"""Minimal Gemini client (REST, no SDK dependency).

Calls the generateContent endpoint with the configured API key/model, optionally
enabling the Google Search grounding tool for fresh team news.
"""
from __future__ import annotations

import httpx

from backend.config import Settings, get_settings

_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiError(RuntimeError):
    pass


class GeminiNotConfigured(GeminiError):
    pass


def is_configured(settings: Settings | None = None) -> bool:
    return bool((settings or get_settings()).gemini_api_key)


def generate_text(
    prompt: str, use_search: bool = False, settings: Settings | None = None
) -> str:
    settings = settings or get_settings()
    if not settings.gemini_api_key:
        raise GeminiNotConfigured("GEMINI_API_KEY is not set.")

    url = f"{_BASE}/{settings.gemini_model}:generateContent"
    headers = {
        "x-goog-api-key": settings.gemini_api_key,
        "content-type": "application/json",
    }
    body: dict = {"contents": [{"parts": [{"text": prompt}]}]}
    if use_search:
        body["tools"] = [{"google_search": {}}]

    try:
        resp = httpx.post(url, json=body, headers=headers, timeout=45.0)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise GeminiError(f"Gemini request failed: {exc}") from exc

    data = resp.json()
    candidates = data.get("candidates") or []
    if not candidates:
        raise GeminiError("Gemini returned no candidates.")
    parts = (candidates[0].get("content") or {}).get("parts") or []
    text = "".join(p.get("text", "") for p in parts).strip()
    if not text:
        raise GeminiError("Gemini returned an empty response.")
    return text
