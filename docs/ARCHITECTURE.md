# RecruiMate — Architecture & Technology Decisions

> Every layer, every choice, and **why X over Y**. Written for someone joining the
> project (or evaluating it) who wants the full picture in one document.

**Stack in one line:** FastAPI + LangGraph + SQLAlchemy/SQLite backend · React + Vite +
Tailwind frontend · custom multi-provider LLM gateway · deterministic-first scoring with
optional LLM blending · 58 tests · GitHub Actions CI · installable PWA.

---

## Table of contents

1. [System architecture](#1-system-architecture)
2. [Two runtime modes](#2-two-runtime-modes-the-core-design-idea)
3. [Request data flow](#3-request-data-flow)
4. [The agent DAG](#4-the-agent-dag)
5. [Backend decisions (X vs Y)](#5-backend-every-x-vs-y-decision)
6. [Auth decisions (X vs Y)](#6-auth-every-x-vs-y)
7. [Frontend decisions (X vs Y)](#7-frontend-every-x-vs-y)
8. [Job import: why these boards](#8-job-import--why-these-two-boards)
9. [Testing & CI](#9-testing--ci)
10. [Product-level decisions](#10-product-level-decisions-the-why-behind-the-why)
11. [Design philosophy](#11-design-philosophy)
12. [Where this could evolve](#12-where-this-could-evolve)

---

## 1. System architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  FRONTEND (React + Vite + Tailwind)  — port 5173 dev / served   │
│  from FastAPI in production                                      │
│  • 14 pages (Dashboard, Job search, Pipeline, Resume,           │
│    Compatibility, Skill gap, Interview prep, Mock interview,     │
│    Tailor, Analytics, Settings, Login…)                          │
│  • axios client with interceptor (bearer token)                  │
│  • React Context for auth state, hooks for everything else       │
├────────────────────────── HTTPS/JSON ────────────────────────────┤
│  API LAYER (FastAPI)  — port 8000                                │
│  • 11 routers, ~45 endpoints, Pydantic request/response schemas  │
│  • middleware: CORS, exception handlers (ValueError→400 etc.)     │
│  • auth dependency (get_current_user) injected per-route         │
├─────────────────────────────────────────────────────────────────┤
│  SERVICE LAYER (pure logic, no HTTP)                             │
│  • skills.py (skill DB + canonicalization)   roadmap_service     │
│  • job_import.py (Remotive/RemoteOK)         tailor_service      │
│  • posting_profile.py (row→JobProfile)       pool_insights       │
│  • resume parsing, embeddings, web fetching (SSRF-guarded)       │
├─────────────────────────────────────────────────────────────────┤
│  AGENT LAYER  (5 specialist agents + supervisor)                 │
│  • Resume · Job · Compatibility · Gap · Interview agents          │
│  • Every agent: deterministic-first, LLM-optional (blended)      │
│  • Supervisor DAG: resume ∥ job → compatibility → gaps →         │
│    interview → report   (LangGraph, with async fallback DAG)     │
├─────────────────────────────────────────────────────────────────┤
│  GATEWAY (custom LLM abstraction)                                │
│  routing → provider adapter → retries/backoff → fallback chain   │
│  → per-user daily budget → usage logging                         │
│  Providers: heuristic │ Groq │ OpenRouter │ Gemini │ Ollama │    │
│             OpenCode server │ custom OpenAI-compatible           │
├─────────────────────────────────────────────────────────────────┤
│  PERSISTENCE                                                     │
│  • SQLAlchemy 2.0 ORM → SQLite file (data/recruimate.db)         │
│  • 13 tables, all user_id-scoped; uploads on disk (uploads/)     │
│  • create_all + ALTER migrations on startup                      │
└─────────────────────────────────────────────────────────────────┘
```

### Directory layout

```
recruimate/
├── backend/
│   ├── app/
│   │   ├── main.py, config.py        # app factory, env settings
│   │   ├── agents/                   # 5 specialist agents + base agent
│   │   ├── gateway/                  # adapters, manager, fallback policy
│   │   ├── graph/                    # LangGraph state, nodes, supervisor
│   │   ├── core/                     # auth primitives, rate limiting
│   │   ├── services/                 # parsing, embeddings, scoring, roadmap,
│   │   │                             # interview, import, insights, tailoring
│   │   ├── api/                      # 11 routers (resume, jobs, pipeline,
│   │   │                             # compatibility, gaps, interviews,
│   │   │                             # providers, dashboard, account, auth…)
│   │   ├── database/                 # models, seed, demo data
│   │   └── prompts/                  # LLM prompt templates
│   ├── tests/                        # 58 tests, offline, no keys
│   └── requirements.txt
├── frontend/
│   ├── src/pages/                    # 14 pages
│   ├── src/components/               # shared UI (ranking, charts, layout)
│   ├── src/services/                 # api.js (axios), auth, utils
│   └── public/                       # manifest, icons (PWA)
├── scripts/make_icons.py             # stdlib-only PNG icon generator
├── .github/workflows/tests.yml       # CI: pytest + vite build
├── .env.example                      # documented configuration
└── README.md
```

---

## 2. Two runtime modes (the core design idea)

```
DEFAULT_PROVIDER=heuristic  ──►  EVERYTHING works offline, zero keys
                                  (resume parse, scoring, roadmap,
                                   interview Q&A, evaluation)

DEFAULT_PROVIDER=groq        ──►  same flow, but agents ask an LLM
                                  where it genuinely helps, and blend
                                  the result with deterministic checks
```

The **same 58-test suite** runs against heuristic mode. That is why CI needs
no API keys and why the app is usable on an airplane.

---

## 3. Request data flow

```
resume.pdf ─► ResumeAgent ─► CandidateProfile (JSON)
                                    │
job board ─► job_import ─► JobPosting (pool) ─► build_job_profile ─► JobProfile
                                    │                                    │
                                    ▼                                    ▼
                        CompatibilityAgent (deterministic weights + embedding sim)
                                    │
                    ┌───────────────┼────────────────┐
                    ▼               ▼                ▼
              ranked matches   GapAnalysisReport  QuestionBank
              (match-resume)   (roadmap+tasks)    (interview)
                    │               │                │
                    ▼               ▼                ▼
              Pipeline        SkillGap page     InterviewSession
              (status/notes)  (task tracking)   (state machine,
                                                 6-dim scoring,
                                                 final report)
```

---

## 4. The agent DAG

```
        ┌── ResumeAgent ──┐     (parallel)
start ──┤                 ├──► CompatibilityAgent ──► GapAgent ──► InterviewAgent ──► report
        └── JobAgent ─────┘
```

- Built with **LangGraph** when installed (typed state, per-node error capture,
  activity trace shown on the Dashboard).
- If LangGraph is missing or broken, an **async fallback orchestrator** runs the
  identical DAG. One definition, two executors.

---

## 5. Backend: every X-vs-Y decision

### Web framework — **FastAPI** vs alternatives

| Alternative | Why not |
|---|---|
| **Flask** | No native async, no request validation, no automatic OpenAPI docs. Would need 4+ extra libraries (marshmallow, flask-cors, …) to match what FastAPI gives for free. |
| **Django (+DRF)** | Batteries-included but heavy: its ORM, admin, app structure. Overkill for a ~45-endpoint JSON API; sync-only request handling fights the async LLM calls. |
| **Express/Fastify (Node)** | Would split the codebase: scoring/agents/NLP are all Python (numpy, embeddings, pypdf). Two languages, two dependency trees, for no gain. |
| **FastAPI** ✅ | Async-native (LLM calls are I/O-bound), Pydantic validation built in, automatic `/docs`, dependency injection maps perfectly onto `get_current_user` / `get_db` / `get_gateway`. |

### Schemas/validation — **Pydantic v2** vs alternatives

| Alternative | Why not |
|---|---|
| **dataclasses** | No validation, no JSON schema, no coercion — all hand-written. |
| **marshmallow** | Schema-only, slower (pure Python), less integrated with FastAPI. |
| **Pydantic v2** ✅ | One declaration validates input, serializes output, generates OpenAPI — and powers `CandidateProfile` / `JobProfile` / `CompatibilityReport`. |

**Key consequence:** `CompatibilityReport` is a Pydantic model, so the *same object*
is what the agent produces, what `generate_roadmap` consumes, what is stored as JSON,
and what the API returns. One source of truth, no DTO mapping layer.

### Orchestration — **LangGraph + fallback DAG** vs alternatives

| Alternative | Why not |
|---|---|
| **CrewAI / AutoGen** | Multi-agent *debate* frameworks — right for adversarial collaboration, wrong here. Our flow is a fixed pipeline: parse → score → plan → interview. Agent autonomy would add nondeterminism we do not want. |
| **Plain async functions** | Works (and we have the fallback), but loses typed shared state, per-node error capture, and the activity trace. |
| **LangGraph** ✅ | Typed `TypedDict` state, parallel branches (resume ∥ job), retries per node — and it degrades gracefully: the app runs identically without it. |

### Database — **SQLite + SQLAlchemy** vs alternatives

| Alternative | Why not |
|---|---|
| **Postgres** | Needs a running server — impossible on Termux, pointless for 1 user. Migrating later = change `DATABASE_URL` + fix naive/aware datetimes (≈1 day). |
| **Supabase** | Bundles *its own auth*, which would replace the JWT layer, not just the DB — a far bigger change than a DB swap. |
| **Raw SQL (sqlite3)** | No models, no migrations, injection risk everywhere; 13 tables hand-written. |
| **MongoDB** | Document DB without schema enforcement; our data is relational (user → resume → compatibility → gap → tasks). |
| **SQLAlchemy 2.0 + SQLite** ✅ | Typed ORM (`Mapped[int]`), relationships with cascades, works everywhere Python runs, zero ops. `DATABASE_URL` is config → Postgres later is a URL swap. |

### LLM layer — **custom gateway** vs alternatives

| Alternative | Why not |
|---|---|
| **LiteLLM** | A whole proxy/service; we need an *in-process library*. Large dependency tree + its own config format for ~300 lines of adapter code. |
| **Provider SDKs directly** | 3+ SDKs with 3 call shapes scattered across 5 agents; no unified fallback, no usage logging, no budget. |
| **OpenAI-compatible-only** | Gemini is not OpenAI-compatible; the OpenCode server is not an inference endpoint at all (session API). |
| **Custom gateway** ✅ | One `generate()` call site; adapter per provider; unified retry/backoff (429-aware); automatic fallback chain; **per-user daily budget**; one `UsageLog` table; `heuristic` is just another provider. |

**Why heuristic is a first-class provider, not a special case:** every code path has
exactly one shape — `gateway.generate()` — so there is no "AI mode" vs "offline mode"
branching anywhere. Zero keys → the same code runs, the heuristic adapter answers.

### Scoring — **deterministic-first, LLM-blended** vs alternatives

| Alternative | Why not |
|---|---|
| **Pure LLM scoring** | Nondeterministic, costs money per score, cannot be unit-tested — and flattery risk (a weak answer can still score 95). |
| **Pure heuristic** | Lexically blind: a strong paraphrase can score 34/100 because the exact keywords are absent. |
| **Deterministic + 60/40 blend** ✅ | Compatibility is **deliberately LLM-free** (weights: skills 40%, experience 25%, projects 20%, education 10%, certs 5% — explainable, stable, testable). Where judgment genuinely matters — *answer evaluation, question generation* — the LLM score is blended 60/40 with deterministic checks and the weighted overall is **always recomputed**, so a model cannot inflate the final number. |

**The split:** compatibility answers "do these two texts overlap?" (measurable →
compute it). Interview answers answer "was this a good answer?" (judgment → ask a
model, but verify).

### Skill/roadmap knowledge — **local curated templates**

| Alternative | Why not |
|---|---|
| **LLM-written roadmaps** | Rule: *"never fabricates course links."* An LLM will happily invent a URL that does not exist — a broken promise. |
| **Scraped course APIs** | Coupling to third-party catalogs, rate limits, dead links over time. |
| **Local knowledge base** ✅ | `skill_template(skill)` returns topics, practice project and base hours from a curated dict. Deterministic, offline, testable, zero dead links. Hours adjust by priority/similarity. |

### Embeddings — **auto with hashed fallback**

| Alternative | Why not |
|---|---|
| **Always sentence-transformers** | ~2 GB of PyTorch — unacceptable on a phone; slow first boot. |
| **No embeddings at all** | Skill matching becomes pure string equality: `k8s ≠ kubernetes`. |
| **`EMBEDDINGS_BACKEND=auto`** ✅ | MiniLM when installed (semantic matching), else **hashed TF-IDF** (pure numpy) — still catches aliases via the canonicalization table; CI uses `hashed` so tests need no model download. |

### HTTP — **httpx** (not `requests`)

`requests` is sync-only. Importing, URL fetching and all LLM calls are awaited on
one event loop; `requests` would block it. `httpx` gives the same API, async, with
per-call timeouts.

### Resume parsing — **pypdf**

| Alternative | Why not |
|---|---|
| **pdfplumber** | Better layout analysis, 3× heavier; we need text extraction + structuring, not table reconstruction. |
| **OCR (tesseract)** | Unreliable on Termux, needs system libs; scanned PDFs are rejected with a clear message — honest failure beats silent garbage. |

### URL safety — **custom SSRF guard**

"Paste a job URL" is a textbook SSRF vector. `utils/web.py` rejects
private/loopback/link-local/metadata addresses (including `169.254.169.254`),
enforces `ALLOWED_CUSTOM_HOSTS`, resolves DNS then checks the resolved IP.
A library exists, but ours is ~40 lines, auditable and tested.

### Rate limiting — **in-memory**

| Alternative | Why not |
|---|---|
| **Redis** | Correct for multi-process/multi-host; we are one uvicorn process on one device. |
| **In-memory dict** ✅ | Honest, zero ops. Documented limitation: counters reset on restart. |

---

## 6. Auth: every X-vs-Y

### Approach — **self-hosted JWT** vs alternatives

| Alternative | Why not |
|---|---|
| **Supabase / Auth0 / Cognito** | External dependency for a local-first app; phones home on every login; useless offline on Termux; user IDs would not map onto our SQLite cleanly. |
| **OAuth (Google login)** | Requires a registered client, redirect flows, and breaks the "works locally with no account" story. Your resume is sensitive — fewer third parties, the better. |
| **Session cookies** | Stateless JWT fits the API-first design (mobile PWA, no server-side session store). |
| **Self-hosted JWT** ✅ | Full control, offline-capable, zero external services — and hardened properly in the security pass. |

### Specific primitives

| Decision | Choice | Rejected alternatives & why |
|---|---|---|
| Password hashing | **bcrypt** (pre-hash for >72 chars) | **argon2** — stronger but `argon2-cffi` is a C extension (painful on Termux); **scrypt/PBKDF2** — stdlib but no PHC strings, more code. bcrypt's >72-char truncation flaw is fixed by pre-hashing long passphrases with SHA-256 first. |
| Access token | **JWT, 60 min, HS256** | Short-lived = small stolen-token window; signed with `JWT_SECRET`; stateless so auth checks need no DB read. |
| Refresh token | **opaque random, 30 days, HMAC-SHA256 stored** | Storing raw refresh tokens = DB leak = takeover. Hashing keyed with `JWT_SECRET` means the DB alone cannot replay them. Legacy SHA-256 fallback kept pre-upgrade sessions alive. |
| Replay protection | **`family_id` revocation** | The standard refresh-rotation flaw: a stolen old token *and* a legitimate refresh can both look valid. Detecting reuse of any token in a family and revoking the whole family is the OWASP-recommended fix. |
| Password policy | 8+ chars, mixed case, digit | NIST now discourages forced complexity rules, but a floor prevents `password123` on a demo-seeded app. |

**Modes:** `AUTH_ENABLED=true` → register/login screens; `false` → trusted-local
mode (no login, one implicit user) — the default in `.env.example`.

---

## 7. Frontend: every X-vs-Y

### Framework — **React (SPA)** vs alternatives

| Alternative | Why not |
|---|---|
| **Next.js** | SSR, file routing, API routes are all *irrelevant*: the API is Python, and the app is a logged-in dashboard with no SEO needs. Adds a Node server next to uvicorn. |
| **Vue / Svelte** | Great libraries; React won on ecosystem breadth (icons, charts, examples) — an availability judgment, not a technical one. |
| **Plain HTML + htmx** | 14 interactive pages with forms, charts and live state (interview state machine) — you would rebuild a framework by hand. |
| **React SPA** ✅ | Client-side routing matches an authenticated dashboard; the API is already JSON; the build output is static files FastAPI serves directly. |

### Build tool — **Vite**

| Alternative | Why not |
|---|---|
| **CRA (react-scripts)** | Officially deprecated; slow builds. |
| **Webpack by hand** | Days of config for a 14-page app. |
| **Vite** ✅ | Sub-second dev server, ~14 s production builds, zero config, one-line dev proxy `/api → :8000`. |

### Styling — **Tailwind**

| Alternative | Why not |
|---|---|
| **Material UI / Chakra** | Opinionated look; fighting the design to make it yours; 200 KB+. |
| **Bootstrap** | Dated look, global CSS conflicts. |
| **Tailwind** ✅ | Utility classes co-located with JSX; the design system is ~10 custom classes (`btn-primary`, `card`, `chip`) in one config; production CSS is purged to what is used. |

### State — **Context + hooks** (verified: no Zustand/Redux/React-Query)

| Alternative | Why not |
|---|---|
| **Redux** | Actions/reducers/selectors boilerplate for global state that is really just *the current user* + *the auth flag*. |
| **Zustand** | A store library for one context value is a dependency you do not need. |
| **TanStack Query** | The strongest "could have" here — genuinely good for server state. Chosen against because pages fetch on mount with `useEffect` and flows are simple (no cache-invalidation gymnastics). A reasonable future upgrade. |
| **Context + hooks** ✅ | Auth in one context; each page owns its data; `api.js` centralizes all HTTP. Minimal model, zero extra deps. |

### HTTP — **axios**

The interceptor attaches the bearer token and handles 401→logout in one place
(vs hand-writing headers on 45 call sites), plus automatic JSON and
`responseType: 'blob'` for the HTML/Markdown exports.

### Charts — **recharts**

Declarative React components, responsive, small. Chart.js is imperative;
raw D3 is far too much work for three trend charts.

### Icons — **lucide-react**

Tree-shakeable (only ~30 imported icons ship), consistent stroke style, MIT.
Font Awesome brings icon-font CSS + licensing tiers for worse DX.

### Routing — **react-router-dom**

An SPA behind auth; file-based routing belongs to frameworks with servers.
Deep links (`/mock-interview/:id`, `/tailor/:jobId`, `/skill-gap?gap=`) are
central to the UX, and `<Routes>` makes them explicit.

---

## 8. Job import — why these two boards

| Alternative | Why not |
|---|---|
| **LinkedIn / Indeed APIs** | No public posting API (LinkedIn closed theirs; Indeed's ToS forbids it) — scraping is fragile and legally grey. |
| **JSearch / RapidAPI aggregators** | Paid, key management, third-party uptime. |
| **Greenhouse / Lever / Ashby APIs** | Only *specific companies'* boards; not searchable by keyword across companies. |
| **Remotive** ✅ | Free public JSON API, **server-side search** (`?search=`), curated remote jobs, explicit tags → perfect for skill extraction. |
| **RemoteOK** ✅ | Free public JSON API, large volume, tags + salary data; needs a User-Agent header and a legal-notice element to skip. |

**Why server-side fixed hosts:** the importer runs against two hardcoded URLs —
zero SSRF surface (contrast with user-supplied job URLs, which go through the
SSRF guard). Upsert-by-URL makes re-imports refresh rather than duplicate.

**Why `raw_text` + `parsed` JSON on one row:** postings are semi-structured.
Storing normalized `raw_text` lets `build_job_profile` *recover* skills and
experience from the description when `parsed` is sparse — board imports often
carry only free text. Flexible schema, no ALTERs when a new board appears.

**Per-candidate pools:** every `job_postings` row carries `user_id`
(`NULL` = shared demo data), so ranking, planning, interviewing and the pipeline
all read one private pool per user, with cross-user access returning 404.

---

## 9. Testing & CI

| Decision | Choice | Rejected & why |
|---|---|---|
| Test runner | **pytest** | `unittest` — verbose, no fixtures/parametrize. |
| Async/loads | `pytest-asyncio` + `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` | The Termux env has a broken `uuid_utils` native module that crashes langsmith's pytest plugin on autoload — disabling autoload is the workaround. |
| Network in tests | **Fake transports** (injected `get()` for the importer, mock transport for gateway adapters) | Hitting real APIs in CI = flaky + key exposure. The suite runs fully offline (`DEFAULT_PROVIDER=heuristic`). |
| Test DB | temp SQLite per session; `AUTH_ENABLED=false`, `SEED_DEMO_ACCOUNTS=false` | Tests must not depend on the developer's `.env` or seed data. |
| CI | **GitHub Actions** — two jobs: backend pytest + frontend `vite build` | Travis (declined for OSS), CircleCI (paid tiers). Actions is free for public repos and lives where the code does. The build job catches JSX breakage without a browser. |
| Coverage philosophy | 58 tests: parsing, scoring, roadmap, interviews, gateway adapters, **privacy isolation (cross-user 404s)**, AI budget, board import, pool, pipeline, insights, tailoring | Tests encode *security properties* (user A can never read user B's rows), not just happy paths. |

**CI proved its worth on day one:** it caught a LangGraph
`InvalidUpdateError` (two parallel nodes writing one un-annotated state key)
that did not reproduce locally — exactly the class of bug CI exists for.

---

## 10. Product-level decisions (the why behind the why)

| Decision | Rationale |
|---|---|
| **Personal target pool per candidate** (not one global job list) | Ranking, plan, interview and pipeline are all *yours*; demo jobs are shared so the app demos well out of the box. |
| **Postings mirrored into `job_analyses` when planning/interviewing** | Reuses history/analytics/compatibility machinery instead of parallel code paths — one data model, three features. |
| **Deterministic tailoring (reorder real bullets, never invent)** | An LLM "improving" your experience is a lie waiting to happen; reordering + tagging your actual bullets is honest and useful. |
| **Cover letter as a *draft*, explicitly labeled** | Same honesty principle: a starting point you edit, not a document to send blind. |
| **Insights = "learn X, unlock N jobs"** | Turns vague "learn more skills" into a ranked ROI list computed from *your actual target jobs*. |
| **Pipeline snapshots posting identity** | Delete the pool row later; application history survives (soft FK, no cascade). |
| **PWA instead of a native app** | Android + Mac, one codebase, installable from Chrome, no Play Store, no build toolchain on the phone. |
| **Daily AI budget (200/user/day, `AI_DAILY_REQUEST_LIMIT`)** | Free tiers die silently; graceful degradation to heuristics keeps the app *working* past the cap instead of erroring. |
| **Security pass** (per-user scoping everywhere, login rate limiting, HMAC refresh + family revocation, startup seeding gated on env) | The app handles resumes (personal data), so auth had to be real, not decorative. |

---

## 11. Design philosophy

> **Deterministic where you can measure, LLM where you must judge, offline where
> you must, honest everywhere** — every layer has a working no-key path, every
> number has an explanation, and no feature fabricates facts (course links,
> resume claims, experience).

---

## 12. Where this could evolve

Not commitments — the honest map of what is next if the project grows:

- **TanStack Query** for server-state caching (replaces per-page `useEffect` fetches)
- **Alembic** migrations (replacing `create_all` + ALTER-on-startup)
- **Redis** rate limiting if it ever runs multi-process
- **Service worker** for a genuinely offline PWA
- **Postgres via Neon/Supabase** if one dataset must span phone + Mac
  (a `DATABASE_URL` swap + naive/aware datetime fixes — about a day)
- **More boards** (Jobicy, Arbeitnow, Hacker News "Who's hiring" via Algolia)
- **Voice answers** in mock interviews (browser Web Speech API)
