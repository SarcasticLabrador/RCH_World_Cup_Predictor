# FIFA World Cup 2026 Predictor

An office prediction game for the 2026 FIFA World Cup. Colleagues predict
scorelines stage by stage, earn points, and compete on a leaderboard.

- **Backend:** FastAPI + SQLAlchemy + SQLite (persistent volume)
- **Frontend:** Streamlit (multi-page app) — *from Phase 2*
- **Auth:** email magic links via Brevo single-sender (no IT/DNS needed) — *Phase 2*
- **Results:** API-Football auto-fetch with manual override — *from Phase 4*
- **AI:** Gemini-powered match centre (REST, optional) — *Phase 7*

## Build phases

| Phase | Scope | Status |
|------:|-------|--------|
| 1 | Repo structure, DB models, FastAPI skeleton, SQLite setup | ✅ done |
| 2 | Auth: whitelist, magic links, email, Streamlit sessions | ✅ done |
| 3 | Predictions: fixture seeding, submission UI, window logic | ✅ done |
| 4 | Results & scoring: API-Football, scoring engine, overrides | ✅ done |
| 5 | Leaderboard & special predictions | ✅ done |
| 6 | Scheduler & reminder emails | ✅ done |
| 7 | Gemini AI match centre | ✅ done |
| 8 | Polish & deploy (Streamlit Cloud + persistent volume) | ⏳ |

## Scoring rules

Match predictions (group + R32–SF): exact score **5 pts**, correct result
only **2 pts** (not additive). The Final's exact score is **15 pts**.
Pre-tournament specials: champion **25**, runner-up **10**, and Golden Ball /
Boot / Glove / Best Young Player / most-goals / fewest-conceded **10 each**.
All point values live in `backend/scoring_config.py` for easy tweaking.

## Local setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env        # then fill in values as phases require them
python -m backend.init_db   # create the SQLite schema

uvicorn backend.main:app --reload
# -> http://127.0.0.1:8000  (docs at /docs, health at /health)

# In a second terminal, run the frontend:
streamlit run frontend/app.py
# -> http://localhost:8501
```

With `EMAIL_PROVIDER=console` (the default), sign-in links are printed to the
backend's console instead of emailed — so you can test login end-to-end with
no API key. Set `EMAIL_PROVIDER=brevo` + `BREVO_API_KEY` + a verified
`EMAIL_FROM` to send real emails.

### Loading fixtures

With `API_FOOTBALL_KEY` set in `.env`, pull the 2026 schedule, teams and
groups from API-Football (idempotent — safe to re-run as the bracket fills in):

```bash
python -m backend.seed_fixtures
```

This can also be triggered from the running API by an admin via
`POST /predictions/admin/seed`. Group-stage predictions open as soon as
fixtures are seeded; knockout windows open after the previous round concludes
(automated in Phase 6).

### Automation (results, reminders, snapshots)

Two ways to run the recurring jobs (refresh results → score → open knockout
windows → email reminders, plus a daily leaderboard snapshot):

1. **In-process scheduler** (default, `SCHEDULER_ENABLED=true`) — APScheduler
   runs inside the backend. Needs an always-on backend.
2. **External cron** — set `SCHEDULER_ENABLED=false` and a `TASK_TOKEN`, then
   have any scheduler (e.g. a free GitHub Actions cron) POST to
   `/tasks/maintenance` and `/tasks/snapshot` with header `X-Task-Token`.
   Works on free hosts that sleep.

Admins can also trigger both manually from the Admin page.

### AI Match Centre

Optional. Set `GEMINI_API_KEY` (and optionally `GEMINI_MODEL`) to enable an
AI briefing of recent results and upcoming fixtures on the Match Centre page.
Without a key, the page still shows fixtures — only the AI prose is hidden.
The "Include latest team news" toggle adds recent team news via Gemini's
Google Search grounding. Uses the Gemini REST API directly (no extra SDK).

## Project layout

```
worldcup-predictor/
├── backend/
│   ├── main.py            # FastAPI app + router wiring
│   ├── config.py          # settings (pydantic-settings, .env)
│   ├── enums.py           # domain enums
│   ├── scoring_config.py  # agreed point values (easy to tweak)
│   ├── security.py        # magic-link + session tokens
│   ├── schemas.py         # API request/response models
│   ├── scheduler.py       # APScheduler: maintenance + daily snapshot
│   ├── init_db.py         # create-schema script
│   ├── seed_fixtures.py   # CLI: seed fixtures from API-Football
│   ├── db/
│   │   ├── base.py        # engine, session, Base, SQLite FK pragma
│   │   ├── types.py       # portable GUID type
│   │   └── models.py      # all ORM models
│   ├── api/
│   │   ├── deps.py        # current-user / admin dependencies
│   │   └── routes/        # health, auth, predictions, admin, specials, leaderboard, tasks, ai
│   └── services/
│       ├── auth.py        # whitelist, users, magic links
│       ├── email.py       # console + Brevo senders
│       ├── email_templates.py
│       ├── football_api.py# API-Football client + parsing
│       ├── seeding.py     # idempotent tournament/teams/matches/windows
│       ├── predictions.py # window state + submission rules
│       ├── scoring.py     # match + special scoring engine
│       ├── results.py     # live results fetch -> seed -> score
│       ├── specials.py    # user awards/champion submission
│       ├── leaderboard.py # overall / per-stage / specials ranking + snapshots
│       ├── tasks.py       # open windows, reminders, snapshot, maintenance
│       ├── gemini.py      # REST Gemini client (+ Google Search grounding)
│       └── match_centre.py# recent/upcoming + AI summary assembly
└── frontend/
    ├── app.py             # Streamlit entry (login + navigation)
    ├── auth.py            # session helpers (require_login)
    ├── api_client.py      # backend HTTP client
    ├── labels.py          # stage/special/scope labels + CET formatting
    └── views/
        ├── home.py        # landing + deadlines
        ├── predictions.py # My Predictions page
        ├── specials.py    # My Picks (awards/champion)
        ├── leaderboard.py # rankings
        ├── match_centre.py# AI Match Centre
        └── admin.py       # results entry, awards, refresh, re-score
```
