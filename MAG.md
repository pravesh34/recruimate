# RecruiMate — Session Handoff (MAG)

**Date:** 2026-11-13
**Repo:** `https://github.com/pravesh34/recruimate.git`
**Branch:** `main`
**Local path:** `/Users/praveshsharna/recruimate`

---

## 1. What this app is

RecruiMate is a **candidate-side AI career & interview coach** (not an ATS — it never
submits applications or contacts employers).

| Module | Outcome |
| --- | --- |
| Resume intelligence | Extracts skills, experience, projects, education from PDF/DOCX/TXT |
| Job intelligence | Splits required vs preferred skills, responsibilities, experience |
| **Job search + ranking** | **NEW** — ranks every posting by compatibility with your resume |
| Compatibility | Explainable weighted score (skills 40%, experience 25%, projects 20%, education 10%, certs 5%) |
| Skill gap | Prioritised roadmap with topics, practice projects, effort estimates, task tracking |
| Interview prep | Technical / project / HR / behavioural questions with expected points |
| Mock interview | One question at a time, follow-ups, six-dimension scoring, final report |
| Analytics | Compatibility trend, interview trend, repeated gaps, study progress |
| **Auth** | **NEW** — accounts, JWT, refresh sessions, per-user data isolation |

**Architecture:** React + Vite + Tailwind frontend · FastAPI + SQLAlchemy + SQLite backend ·
LangGraph supervisor (with async-fallback orchestrator) · Unified LLM gateway
(OpenRouter / Groq / Gemini / OpenCode / Ollama / custom / heuristic offline).

---

## 2. ✅ DONE this session

### 2.1 API keys configured (`.env`)

All four remote providers now have keys, stored in the gitignored `.env`.
**The real values are intentionally not in this file.** Get them from your own
`.env` (see `.env.example` for the shape) or re-issue them.

```env
OPENROUTER_API_KEY=<your-openrouter-key>
GROQ_API_KEY=<your-groq-key>
GEMINI_API_KEY=<your-gemini-key>
DEFAULT_PROVIDER=ollama
```

> ⚠️ These keys were shared in chat and are compromised. **Rotate all three
> before any public deploy** and keep them in environment secrets, never in git.

### 2.2 Job search + compatibility ranking (NEW feature)

**Backend** — `backend/app/api/jobs.py` → `GET /api/jobs/match-resume?resume_id=N`

- Scores every row in `job_postings` against the signed-in user's resume
- Uses the existing deterministic `CompatibilityAgent` (no LLM call, no cost)
- Auto-recovers skills from job descriptions: strips HTML, canonicalises aliases via
  `services/skills.extract_skills`
- Auto-detects minimum experience with `r"(\d+)\s*\+?\s*years"`
- Returns jobs sorted by score with `rank`, `verdict`, `matched_skills`,
  `partial_skills`, `missing_skills`, `evidence`, `strengths`, `concerns`, `explanation`
  and the posting `url` (for an Apply link)

> ⚠️ Route ordering matters: this endpoint lives in `jobs.py` **before** `@router.get("/{job_id}")`.
> Putting it in another router causes a 422 (the `{job_id}` path swallows `match-resume`).

**Frontend**
- `frontend/src/components/JobMatchRanking.jsx` — NEW reusable ranked list
  (score badge, filter chips All/Strong/Stretch/Below-30, expandable "Why?" panel, Apply link)
- `frontend/src/pages/JobSearch.jsx` — NEW dedicated `/jobs` page with a resume selector
- `frontend/src/pages/Dashboard.jsx` — "Recent job analyses" panel replaced by the
  ranked-jobs panel; hero CTA now "Find jobs for me"
- `frontend/src/components/Layout.jsx` — "Job search" added to sidebar nav
- `frontend/src/App.jsx` — `/jobs` route added

### 2.3 Demo job postings

`backend/scripts/seed_demo_jobs.py` — 8 seeded roles with structured `parsed` skills
(ML Engineer, AI Research Intern, LLM Evaluation Specialist, Data Scientist,
Backend Engineer, Full Stack Developer, Deep Learning Engineer, AI Solutions Consultant).
Idempotent (re-runnable, updates in place).

```bash
cd backend && python3 scripts/seed_demo_jobs.py
```

### 2.4 Full auth system (NEW)

**Backend**
- `backend/app/core/auth.py` — NEW. bcrypt hashing (direct `bcrypt` lib, **not** passlib —
  passlib 1.7.4 breaks on bcrypt ≥ 4.1), JWT access tokens via `python-jose`,
  opaque hashed refresh tokens, password policy.
- `backend/app/api/auth.py` — NEW router. Endpoints:
  | Method | Path | Purpose |
  | --- | --- | --- |
  | GET | `/api/auth/status` | Is auth on? How many demo accounts? |
  | POST | `/api/auth/register` | Create account → tokens |
  | POST | `/api/auth/login` | Credentials → tokens |
  | POST | `/api/auth/refresh` | Rotate refresh token → new access token |
  | POST | `/api/auth/logout` | Revoke a refresh session |
  | GET | `/api/auth/me` | Current account |
  | GET | `/api/auth/sessions` | List sessions |
  | POST | `/api/auth/sessions/{id}/revoke` | Revoke one session |
  | POST | `/api/auth/change-password` | Change password, revoke other sessions |
- `backend/app/api/deps.py` — `get_current_user` dependency added. Resolution order:
  JWT → legacy shared `API_TOKEN` → local candidate (trusted-local mode).
- `backend/app/database/models.py` — `User` gained `password_hash`, `role`, `is_active`,
  `is_demo`, `last_login_at`. New `AuthSession` table. `init_db()` now runs
  `_apply_column_migrations()` so new columns are ALTERed onto an existing SQLite file.
- Per-user data isolation applied to `resume`, `jobs`, `compatibility`, `dashboard` routers.

**Config** (`.env`)
```env
AUTH_ENABLED=true
JWT_SECRET=recruimate-local-dev-secret-change-in-production
ACCESS_TOKEN_MINUTES=60
REFRESH_TOKEN_DAYS=30
SEED_DEMO_ACCOUNTS=true
DEMO_ACCOUNT_PASSWORD=RecruiMate@123
```

**Frontend**
- `frontend/src/services/auth.jsx` — NEW `AuthProvider` + `useAuth` hook
- `frontend/src/services/api.js` — token store, request interceptor (bearer), 401 →
  silent refresh → retry, plus `api.authStatus/login/register/logout/me/...`
- `frontend/src/pages/Login.jsx` — NEW sign-in / register screen with one-click demo accounts
- `frontend/src/App.jsx` — `AuthProvider` wraps the app, `/login` route, `RequireAuth` guard
- `frontend/src/components/Layout.jsx` — user chip + sign-out button in the sidebar

### 2.5 Five demo candidates

`backend/scripts/seed_demo_candidates.py` — creates 5 accounts, each with a distinct
resume profile (skills, experience, education, projects) so ranking results differ
meaningfully per person.

| Email | Name | Persona | Password |
| --- | --- | --- | --- |
| `candidate1@example.com` | Aarav Sharma | AI/ML undergrad, 0 yrs | `RecruiMate@123` |
| `candidate2@example.com` | Diya Patel | Data scientist, 3 yrs | `RecruiMate@123` |
| `candidate3@example.com` | Arjun Menon | Backend engineer, 4 yrs | `RecruiMate@123` |
| `candidate4@example.com` | Ishita Rao | MLOps engineer, 2 yrs | `RecruiMate@123` |
| `candidate5@example.com` | Kabir Nair | LLM engineer, 2 yrs | `RecruiMate@123` |

```bash
cd backend && python3 scripts/seed_demo_candidates.py
```

**Verified ranking differs per candidate:**
```
candidate1 (student)  → AI Research Intern          62.5
candidate5 (LLM eng)  → LLM Evaluation Specialist   81.1
```

---

## 3. ⬜ TODO / next steps

### Priority 1 — finish user-scoping (partially done)
`resume`, `jobs`, `compatibility`, `dashboard` are user-scoped.
**Still to check/scope:**
- `backend/app/api/skill_gaps.py`
- `backend/app/api/interviews.py`
- `backend/app/api/providers.py`
- `backend/app/api/account.py` (`DELETE /api/account/data` must only delete the caller's rows)
- `job_postings` table is currently **global** — decide whether postings are per-user or shared

### Priority 2 — auth hardening
- [ ] Hash the refresh token with a keyed hash (SHA-256 is acceptable for high-entropy
      tokens, but HMAC is better)
- [ ] Add rate limiting on `/api/auth/login` (lockout after N failures)
- [ ] Move `JWT_SECRET` to a real secret store, rotate the dev value
- [ ] Add `AUTH_ENABLED` gate so `AUTO_SEED` only runs when auth is on
- [ ] Refresh-token reuse detection (revoke the whole family on replay)

### Priority 3 — seeds
- [ ] Call `seed_demo_candidates()` / `seed_demo_jobs()` from `init_db()` when
      `SEED_DEMO_ACCOUNTS=true`, so a fresh clone is usable immediately
- [ ] Add a `--reset` flag to drop and re-seed

### Priority 4 — product
- [ ] Job postings import pipeline (RemoteOK / a real board) — currently seeded by hand
- [ ] "Apply" flow: tailor resume + cover letter per job, export PDF
- [ ] Persist a `job_matches` row per (user, job) so rankings are incremental, not recomputed
- [ ] Filter jobs by location / remote / type / salary in the ranking UI
- [ ] Settings page: change password + session list UI (backend endpoints already exist)

### Priority 5 — correctness / quality
- [ ] `backend/tests/` — add auth tests (register, login, refresh rotation, revoke,
      cross-user 404s) and ranking tests
- [ ] The compatibility score rewards jobs with *fewer* required skills (coverage ratio),
      so a job with no skills listed can outrank a good match. Consider a confidence
      floor: postings with < 3 extracted skills should be flagged "low confidence".
- [ ] Duplicate job postings (same title from the same board) are not de-duplicated

---

## 4. Run it

```bash
cd /Users/praveshsharna/recruimate/backend
source .venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

```bash
cd /Users/praveshsharna/recruimate/frontend
npm run dev     # http://127.0.0.1:5173
```

| URL | What |
| --- | --- |
| http://127.0.0.1:5173 | App (redirects to `/login`) |
| http://127.0.0.1:5173/login | Sign in / register |
| http://127.0.0.1:5173/jobs | **Job search + ranking** |
| http://127.0.0.1:8000/api/docs | Swagger |
| http://127.0.0.1:8000/api/health | Health (shows `"auth":"accounts"`) |
| http://127.0.0.1:8000/api/auth/status | Auth status |

**Stop:** `pkill -9 -f uvicorn` and `pkill -9 -f "vite --host"`

---

## 5. Files changed this session

```
backend/app/api/auth.py              NEW
backend/app/api/deps.py              MOD  get_current_user dependency
backend/app/api/jobs.py              MOD  match-resume endpoint + user scoping
backend/app/api/compatibility.py     MOD  user scoping
backend/app/api/resume.py            MOD  user scoping
backend/app/api/dashboard.py         MOD  user scoping
backend/app/api/schemas.py           MOD  JobMatch schema
backend/app/core/auth.py             NEW  bcrypt/JWT/refresh primitives
backend/app/core/__init__.py         NEW
backend/app/config.py                MOD  auth settings
backend/app/database/models.py       MOD  User auth columns + AuthSession + migrations
backend/app/main.py                  MOD  auth router + health field
backend/requirements.txt             MOD  bcrypt, python-jose
backend/scripts/seed_demo_jobs.py    NEW
backend/scripts/seed_demo_candidates.py NEW
frontend/src/App.jsx                 MOD  auth provider + /login + RequireAuth
frontend/src/components/JobMatchRanking.jsx NEW
frontend/src/components/Layout.jsx   MOD  nav item + user chip + sign out
frontend/src/pages/Dashboard.jsx     MOD  ranked jobs panel
frontend/src/pages/JobSearch.jsx     NEW
frontend/src/pages/Login.jsx         NEW
frontend/src/services/api.js         MOD  token store, interceptors, auth methods
frontend/src/services/auth.jsx       NEW
.env                                MOD  all API keys + auth config
```

---

## 6. ⚠️ Security notes before any public deploy

1. **Rotate every API key in `.env`** — they were shared in chat and are in git history
   once pushed. Use environment secrets, not the file.
2. Set a strong `JWT_SECRET` (32+ random bytes).
3. Set `ALLOWED_CUSTOM_HOSTS` to an empty/narrow list and `ALLOW_PRIVATE_HOSTS=false`.
4. Add rate limiting on the auth endpoints.
5. Serve over HTTPS only; set `CORS_ORIGINS` to the real origin.
