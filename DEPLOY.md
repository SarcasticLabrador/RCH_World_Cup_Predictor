# Deployment guide (free, Option A)

Architecture: **Streamlit Community Cloud** (frontend) → **Render free** (FastAPI
backend) → **Neon** (Postgres). Recurring jobs run via **GitHub Actions cron**.
Everything below is $0.

```
 Browser ──▶ Streamlit Cloud (frontend) ──httpx──▶ Render (FastAPI) ──▶ Neon (Postgres)
                                                        ▲
                              GitHub Actions cron ──────┘  (/tasks/maintenance, /tasks/snapshot)
```

No CORS setup is needed: the Streamlit server calls the backend server-side
(not from the browser).

## 1. Database — Neon (free Postgres)

1. Create a project at neon.tech (no card needed).
2. Copy the connection string. You can paste it as-is — the backend rewrites a
   `postgresql://...` URL to the psycopg driver automatically. (The explicit
   `postgresql+psycopg://USER:PASSWORD@HOST/DBNAME?sslmode=require` form also
   works.) Make sure `sslmode=require` is present (Neon includes it by default).
3. Keep it for the backend's `DATABASE_URL`.

Neon scale-to-zero suspends the DB after ~5 min idle and auto-resumes on the
next query (~1–2s). The backend uses `pool_pre_ping` so this is transparent.

## 2. Backend — Render (free web service)

1. Push this repo to GitHub (private is fine).
2. In Render: **New → Blueprint**, select the repo. It reads `render.yaml`.
3. After it creates the service, open **Environment** and set the `sync: false`
   values:
   - `DATABASE_URL` — the Neon string from step 1
   - `APP_BASE_URL` — your Streamlit app URL (from step 3), e.g.
     `https://your-app.streamlit.app`
   - `BREVO_API_KEY`, `EMAIL_FROM` — your Brevo single-sender (see Phase 2)
   - `EMAIL_WHITELIST` — e.g. `@yourcompany.com`
   - `ADMIN_EMAILS` — your email (grants you admin on first login)
   - `API_FOOTBALL_KEY` — from api-football.com
   - `GEMINI_API_KEY` — optional, enables the AI Match Centre
   - `SECRET_KEY` and `TASK_TOKEN` are auto-generated — copy `TASK_TOKEN` for step 4.
4. Tables are created automatically on first boot. Then seed fixtures once:
   open the API docs at `https://<your-render-url>/docs` and run
   `POST /predictions/admin/seed` (as admin), or run `python -m backend.seed_fixtures`
   locally against the same `DATABASE_URL`.

The free service sleeps after 15 min idle; the first request then waits ~30–60s
to wake. The 2-hourly maintenance cron keeps it warm during match days.

## 3. Frontend — Streamlit Community Cloud

1. In share.streamlit.io: **New app**, point it at `frontend/app.py` on this repo.
2. In **App → Settings → Secrets**, add (TOML):
   ```toml
   BACKEND_URL = "https://<your-render-url>"
   ```
3. Deploy. Note the app URL and make sure it matches `APP_BASE_URL` on Render
   (magic-link and reminder emails are built from it).

## 4. Scheduler — GitHub Actions

The workflow `.github/workflows/maintenance.yml` is already in the repo. Add two
repository secrets (**Settings → Secrets and variables → Actions**):
- `BACKEND_URL` — your Render URL
- `TASK_TOKEN` — the value Render generated

It runs maintenance every 2 hours and a leaderboard snapshot daily at 04:00 UTC
(≈06:00 CEST). You can also trigger it manually (**Actions → Run workflow**).

Notes: GitHub's scheduled runs can be delayed at peak times, and scheduled
workflows pause after 60 days of repo inactivity — neither matters for a
six-week tournament. Private-repo Actions minutes are ample for these tiny jobs.

## 5. Go-live checklist

- [ ] Neon DB created; `DATABASE_URL` set on Render
- [ ] Render backend deployed; `/health` returns ok
- [ ] Brevo single-sender verified; a test magic link arrives
- [ ] `ADMIN_EMAILS` includes you; you see the Admin page
- [ ] Fixtures seeded; group predictions open
- [ ] Streamlit app deployed; `BACKEND_URL` secret set; `APP_BASE_URL` matches
- [ ] GitHub Actions secrets set; manual run of the workflow succeeds

## Cost & limits summary

| Piece | Free limit that matters |
|---|---|
| Render web service | sleeps after 15 min; 750 instance-hours/month (ample with sleep) |
| Neon Postgres | 0.5 GB storage; auto-suspend/resume |
| Streamlit Cloud | sleeps when idle, wakes on visit |
| GitHub Actions | minutes quota (tiny curl jobs); possible schedule delay |
| Brevo email | ~300 emails/day |
| API-Football | ~100 requests/day (the 2-hourly poll is well within) |
