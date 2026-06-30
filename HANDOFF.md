# Orrin — Handoff Document

> Consolidated from HANDOFF.md, HANDOFF_1.md, HANDOFF_2.md, and CLAUDE.md (all previously living in Downloads, none in the repo). This version was cross-checked directly against the live code in `D:\orrin` as of 2026-06-30 — claims that turned out to be unverified or wrong in the source docs have been corrected, with notes on what changed. Read this before touching code.

---

## 1. Product Vision

Orrin is an AI operational-intelligence tool for early-stage startups. It connects to Slack and Linear, indexes messages and tickets, and answers plain-English questions like *"why is the onboarding redesign delayed?"* with a synthesized answer, a confidence score, and cited sources — eliminating the need to manually search across both tools.

**One-liner:** Ask your company anything. Orrin connects Slack and Linear so founders get instant, evidence-backed answers instead of searching through conversations and tickets.

**Example questions it should answer well:**
- Why is feature X delayed?
- What is blocking onboarding?
- What changed this week?
- What is customer Y waiting for?

**YC framing:** Matches YC Summer 2026 RFS category "Company Brain." Target: YC W27 application (~Oct 2026).

**V1 scope is deliberately narrow:** answer operational questions from synced Slack/Linear data, with sources. It does NOT create tickets, send reminders, automate workflows, generate reports, manage projects, or act as a general chatbot. Resist scope creep even if it seems easy to add — the differentiator is evidence-backed answers with honest confidence scoring, not feature breadth.

---

## 2. Product Principles (do not violate these)

- Founder-first, not enterprise-first
- Fast to use — answers in seconds, not a research tool
- Simple UI over feature density
- **AI answers must always cite sources.** Never ship a change that lets Orrin answer without showing which Slack messages / Linear issues it used as evidence. This is the core trust mechanism of the product.

---

## 3. Founder Context

- First-time solo founder, fresher graduating Sep 2026
- AI/ML background; prior projects: multi-agent research engine, fare prediction, Quiz Master (Flask/Jinja/SQLite)
- Not deeply experienced in MERN/MEAN/TypeScript — builds with Flask, AI-assisted coding (Cursor), strong product instincts (PRDs, wireframes, user research)
- Zero/near-zero budget — every tool choice filtered through "is this free or near-free"
- Prefers being told exactly what to do step-by-step during debugging (exact button names, exact file locations) rather than abstract instructions. Pushes back on overbuilt/premature work — respect that instinct rather than over-engineering.

---

## 4. Product Identity

- **Name:** Orrin
- **Domain:** getorrin.xyz (Namecheap), live at **https://www.getorrin.xyz**. Railway's plan only allows one custom domain; bare `getorrin.xyz` uses a Namecheap redirect rather than a true Railway domain.
- **Logo:** Three coral/salmon triangles forming an abstract "M"/mountain shape on deep purple, paired with lowercase "orrin" wordmark. `orrin-logo.png` in `app/static/`. Favicon set fully implemented.
- **Design language:** Dark theme, near-black background (#0b0d12), refined blue accent (#4f7df9), Geist font, card-based UI with subtle borders (#22252e).
- **Hero badge:** Deliberately does NOT claim "Backed by Y Combinator" — Orrin is applying to YC, not admitted. **Do not re-add a YC-backing claim unless/until actually admitted.**

---

## 5. Architecture (verified directly against repo, 2026-06-30)

Single flat Flask app — **not** a `backend/services/integrations` layered architecture some older summaries described.

```
orrin/
├── app/
│   ├── __init__.py       # App factory: OAuth registration (Google/Slack/Linear), Sentry, PostHog (sync_mode=True), ProxyFix, rate limiter, CSRF, logging
│   ├── routes.py         # ALL routes in one Blueprint (`main`), get_current_user() IDOR-safe helper
│   ├── models.py         # User, SlackMessage, LinearIssue
│   ├── sync.py           # sync_slack_data(), sync_linear_data() — real API calls, name resolution, dedup
│   ├── ai.py             # MOCK_MODE flag, build_context(), ask_orrin() — Gemini primary + Groq fallback, _generate_mock_answer()
│   ├── templates/
│   │   ├── layout.html   # Base template (navbar/footer), extended by index/login/connect
│   │   ├── index.html
│   │   ├── login.html
│   │   ├── connect.html  # Slack/Linear connect cards + bot-invite warning banner
│   │   └── dashboard.html # Standalone — own html/head/body, sidebar layout, NOT extending layout.html
│   └── static/
│       ├── css/style.css # Hand-written, no framework
│       └── orrin-logo.png, favicon set
├── requirements.txt
├── Procfile               # web: gunicorn run:app --timeout 60   [CONFIRMED in repo]
├── run.py                 # create_app() + db.create_all()
└── .env / .gitignore
```

No `services/` or `integrations/` folder exists or is planned at this scale. Given the founder's stated preference for "small services over huge files," if `routes.py` grows, prefer splitting into multiple blueprint files (`auth_routes.py`, `dashboard_routes.py`) over a deeper folder hierarchy.

**Data flow:** User logs in via Google → connects Slack and/or Linear (single-tool onboarding, not both required) → `dashboard_ask` route triggers an auto-sync (throttled to once/60s via `last_synced_at`) → `sync_slack_data()` / `sync_linear_data()` pull fresh messages/issues → `build_context()` in `ai.py` assembles the 100 most recent Slack messages + 50 most recent Linear issues across all connected channels/teams → question + context goes to Gemini (3x retry) → Groq fallback if Gemini fails entirely → honest "high demand" message with retry button if both fail → structured JSON answer with confidence + cited source indexes → rendered in `dashboard.html`.

---

## 6. Tech Stack (verified)

- **Backend:** Python + Flask, Blueprint pattern
- **Database:** SQLite locally (`orrin.db`), Postgres in production (Railway `DATABASE_URL`, auto-detected, `postgres://` rewritten to `postgresql://`)
- **ORM:** Flask-SQLAlchemy
- **Auth:** Authlib OAuth (Google, Slack, Linear), Flask session-based. `session['user_email']` is the only source of truth for identity. `flask-login` is listed in requirements.txt but is dead weight — not actually used.
- **AI:** Google Gemini via `google-genai` SDK (NOT the deprecated `google-generativeai`), model `gemini-2.5-flash-lite`. **Fallback: Groq** (`llama-3.3-70b-versatile` via OpenAI-compatible client) if Gemini fails after 3 retries — confirmed present in `ai.py`, deliberately stopped at two providers.
- **Frontend:** Server-rendered Jinja2, hand-written CSS, no JS framework. Minimal vanilla JS for the "thinking overlay" and suggested-question buttons.
- **Security:** Flask-Limiter (in-memory store, known limitation), Flask-WTF (CSRF), hardened session cookies (HttpOnly, SameSite=Lax, Secure in prod), 24h session expiry.
- **Monitoring:** Sentry (production-only). PostHog (production-only, `sync_mode=True` — required because Railway's gunicorn workers can recycle before a buffered event flushes).
- **Deployment:** Railway, `Procfile` (`web: gunicorn run:app --timeout 60`), custom domain `www.getorrin.xyz`.

---

## 7. Database Schema (app/models.py)

- **User** — id, email, name, picture, slack_team_id, slack_team_name, slack_bot_token, linear_access_token, linear_workspace_name, last_synced_at
- **SlackMessage** — id, user_id (FK), channel_id, channel_name, message_text, author, posted_at, synced_at
- **LinearIssue** — id, user_id (FK), issue_identifier, title, description, status, assignee, updated_at, synced_at

**Logout behavior:** `logout()` only does `session.clear()`. It has never cleared `slack_bot_token`/`linear_access_token` from the DB. This is correct, intended behavior (matches Slack/Gmail itself) — connections persist across logout/login for the same account. **Do not "fix" this.**

---

## 8. Key Architectural Decisions (each tied to a real bug — don't reverse without understanding why)

1. **`get_current_user()` is the ONLY way any route fetches the logged-in user.** Derives identity strictly from `session['user_email']`, never from request params (IDOR protection). Auto-clears stale sessions pointing at deleted users.
2. **Single-tool onboarding.** Users reach the dashboard with just Slack OR just Linear connected — deliberate adoption-friction fix after a "both required" gate blocked early users.
3. **Auto-sync before every question, throttled to 60s** via `User.last_synced_at`. Replaced a manual-only `/sync` flow after a real staleness bug (fresh Slack messages invisible because nobody remembered to sync).
4. **`MOCK_MODE` in `ai.py`.** Currently `False` (real AI is live). Lets the whole pipeline be tested for $0 against real synced data with rule-based fake answers. If re-enabled, its fallback message text must stay in sync with the real path's — they currently match (both say the old "Connect Slack or Linear" text, see open items below).
5. **Gemini over Claude:** ~30x cheaper per token, free tier sufficient at zero-revenue stage. Revisit post-funding/revenue, not before.
6. **`google-genai` SDK, not `google-generativeai`** — the latter is deprecated/sunset and caused `DefaultCredentialsError` in production from internal credential-discovery bugs. This was NOT a wrong API key, it was a broken library.
7. **Gemini key format:** keys starting `AQ.` are correct as of the 2026 key migration, not `AIzaSy...`. Not a mistake.
8. **Retry logic with exponential backoff (3 attempts, 1s/2s/4s)** around the Gemini call, then Groq fallback, then an honest "high demand" message — handles free-tier 503 overload gracefully without a hard crash.
9. **Linear OAuth requires `token_endpoint_auth_method: 'client_secret_post'`** explicitly set in Authlib client registration (`app/__init__.py:116`, confirmed present). Without it, Linear's token endpoint returns `invalid_secret` — NOT because credentials are wrong, but because Authlib defaults to HTTP Basic Auth, which Linear's token endpoint rejects. **If this error reappears, check this setting before regenerating any secrets.**
10. **`gunicorn` needs `--timeout 60`** in the Procfile (confirmed present). Default 30s timeout was killing worker processes mid-Gemini-retry, producing a hard crash that bypassed all graceful-fallback logic entirely (a killed gunicorn worker is not a Python exception — no try/except can catch it).
11. **Linear access tokens are sent without a `Bearer ` prefix** in `sync.py`/`routes.py` (confirmed: `Authorization: <token>`, not `Authorization: Bearer <token>`). Technically non-compliant with Linear's documented format, but confirmed working in live testing. Founder explicitly chose not to change it. **Do not silently "fix" this — get explicit sign-off first.**
12. **Slack bot must be manually invited to each channel** (`/invite @Orrin` or channel → Integrations tab → Add an app) — a Slack platform constraint, not a bug. `connect.html` has an on-page callout explaining this after a real bug where `#social` messages were invisible because the bot was never invited there.

---

## 9. Open Bugs / Threads (status corrected against live code, 2026-06-30)

### OPEN — `dashboard_ask` has no error-handling wrap
A try/except around the sync calls + `ask_orrin()` in `dashboard_ask` (`routes.py`) was discussed and written as a suggestion in a prior session, intended to route any unexpected non-Gemini exception to a friendly fallback message + Sentry capture. **Checked directly against `app/routes.py` on 2026-06-30 — this was never actually applied.** Still needs to be written and deployed.

### OPEN — "No synced data" message doesn't mention the invite step
A clearer fallback message (explicitly telling users to check `/invite @Orrin`) was discussed for `ask_orrin()` and `_generate_mock_answer()` in `ai.py`. **Checked directly against `app/ai.py` on 2026-06-30 — both still say the old text:** *"There's no synced data yet. Connect Slack or Linear, then try asking again."* Still needs to be written and deployed.

### NEEDS VERIFICATION (external, not visible in repo) — Which Slack app is actually live
Two Slack apps both named "Orrin" exist:
- **OrrinDev workspace app** — the original. Older notes describe this as the one wired into the live codebase and invited into `#all-orrindev`.
- **Ignitus workspace app**, App ID `A0BCKQC6L2C`, Client ID `261581676610.11427828224080` — created to fix `invalid_team_for_non_distributed_app` (the original app couldn't get Public Distribution activated). A later session describes swapping `SLACK_CLIENT_ID`/`SLACK_CLIENT_SECRET` in Railway to point to this app instead.

**These two accounts contradict each other on which app is currently live in production.** Channel invites do NOT transfer between the two bot identities. Before doing any Slack-related debugging: confirm in Railway's actual env vars which `SLACK_CLIENT_ID` is set, then confirm that app has been added (via channel → Integrations tab → Add an app, not `/invite`, since that command can resolve to the wrong same-named app) to every channel being tested.

### NEEDS VERIFICATION (external, not visible in repo) — Linear credentials swap
The original Linear OAuth app was permanently locked to "Private to this workspace" (Linear doesn't allow flipping this post-creation). A new public-distribution app was created via `https://linear.app/settings/api/applications/new?distribution=public`. **Not confirmed: whether `LINEAR_CLIENT_ID`/`LINEAR_CLIENT_SECRET` in Railway were actually updated to the new app's values, or whether a redeploy + end-to-end retest happened.** Verify before assuming outside users can connect Linear.

### RESOLVED — Linear `invalid_secret` OAuth error
Root cause: Authlib defaulted to HTTP Basic Auth for the token exchange; Linear requires `client_secret_post`. Fix confirmed present in `app/__init__.py:116`.

### RESOLVED — Gunicorn worker timeout crashing requests as raw 500 pages
Root cause: default 30s gunicorn timeout killed the worker mid-Gemini-retry. Fix confirmed present in `Procfile`.

### RESOLVED (per most recent session narrative, not independently verifiable from repo) — Slack cross-workspace install failure (`invalid_team_for_non_distributed_app`)
Root cause: Slack app wasn't publicly distributed. Reportedly fixed by activating Public Distribution on the Ignitus app after removing a stray `http://localhost:5000` redirect URL blocking the "Use HTTPS For Your Features" checklist item. Side effect: the Slack-app-identity confusion bug above.

### RESOLVED (per most recent session narrative) — Dashboard sidebar nav drifting downward
Root cause: `.dash-sidebar` had no independent height, stretched to match `.dash-main`, and `justify-content: space-between` re-spread nav items. Fixed via `position: sticky; top: 0; height: 100vh; align-self: flex-start;` plus `margin-top: auto` on `.dash-sidebar-bottom`. Not independently re-verified visually against the current `style.css` in this pass — worth a visual check, not a code-presence check.

### RESOLVED — `#social` Slack sync bug
Root cause: bot was never invited to `#social`, only to `#all-orrindev`. Fixed via `/invite @Orrin` at a time when the OrrinDev app was still active. Validity should be re-checked once the Slack app identity question above is resolved.

---

## 10. Known Limitations (carried over, still true)

- Rate limiting uses in-memory storage, not Redis — resets on every redeploy, doesn't share state across multiple workers/instances. Acceptable at current scale; revisit once real concurrent traffic exists.
- `build_context()` pulls the 100 most recent Slack messages + 50 most recent Linear issues, ordered by pure recency across ALL connected channels combined (confirmed in `ai.py`). Fine at low usage; older/less-active-channel messages will silently fall outside this window with no warning as usage grows.
- Railway's plan allows only one custom domain; bare `getorrin.xyz` uses a Namecheap redirect, not a true Railway domain.
- No mechanism currently surfaces to users which Slack channels Orrin can/can't see — they must remember to invite the bot manually to every new channel. A V2 feature could surface this in-dashboard instead of relying on the warning banner.
- `flask-login` in `requirements.txt` is unused — session-based auth is hand-rolled via `get_current_user()`. Harmless but could be removed.
- Whether the frontend PostHog pageview/session-tracking snippet is installed (vs. just backend `posthog.capture()` custom events, which are confirmed working) was unclear as of the last session — verify directly in PostHog's Web Analytics tab.

---

## 11. Things Future Sessions Should NEVER Change Without Being Explicitly Asked

- **Do not add a "Backed by Y Combinator" badge or claim** in any form until/unless Orrin is actually admitted.
- **Do not regenerate Linear's client secret to "fix" `invalid_secret`.** The actual root cause was the missing `client_secret_post` auth method, already fixed in code. Regenerating secrets will not help and is not the fix.
- **Do not silently change the missing-`Bearer`-prefix behavior on Linear API calls** without explicit founder sign-off — deliberately left as-is, confirmed working.
- **Do not assume `/logout` clears Slack/Linear connections.** It never has, in any commit — this is correct, intended behavior, not a bug.
- **Do not reopen V1 scope** to add ticket creation, reminders, workflow automation, or general chatbot behavior.
- **Do not switch the AI provider away from Gemini-primary/Groq-fallback** without being asked — a deliberate cost decision under real budget constraints.
- **Do not re-require both Slack AND Linear before allowing dashboard access** — deliberately removed.
- **Do not remove the auto-sync-before-asking behavior** without replacing it with an equivalent freshness guarantee.
- **Do not restructure the file layout** (splitting `routes.py`, adding `services/`) without being asked — the flat structure is intentional at this size.
- **Do not remove or weaken the IDOR-safe `get_current_user()` pattern.**
- **Do not remove source citation from AI answers** — core to the product's trust model, not a nice-to-have.
- **Do not assume a single "Orrin" Slack app exists** until the consolidation TODO below is done — there are currently two, and conflating them already caused a real, time-costing bug.
- **Do not treat the two "OPEN" items in section 9 as done** without first checking the live deployed code — they were written as suggestions in conversation but never actually applied to `routes.py`/`ai.py`.

---

## 12. Current TODOs, in priority order

1. Resolve which Slack app is actually live in Railway right now (see section 9) — this blocks all further Slack debugging.
2. Verify the live Slack app has been added (via Integrations tab) to every channel currently being tested against.
3. Verify `LINEAR_CLIENT_ID`/`LINEAR_CLIENT_SECRET` were swapped to the new public-distribution Linear app and redeployed.
4. Actually apply the two still-open code fixes: the `routes.py` try/except wrap around `dashboard_ask`, and the `/invite @Orrin` mention in `ai.py`'s no-data fallback message (both in section 9).
5. Re-test the full Linear connect → ask → cited-answer flow end-to-end with a genuinely new outside account, the same way Slack was validated.
6. Decide whether to consolidate down to a single Slack app (delete the orphaned one) before any serious onboarding push.
7. Get 2-3 real strangers (not friends) to test the live product end to end, and watch what they actually ask.
8. Improve retrieval quality based on real usage patterns.
9. UX polish based on observed real-user friction.
10. YC application, using real usage evidence from the above.
11. Production hardening (Redis-backed rate limiting) only once real concurrent traffic justifies it.

---

## 13. Files Most Recently Touched (rough chronological order, across sessions)

`app/ai.py` (Gemini SDK migration, retry logic, Groq fallback), `app/routes.py` (auto-sync, PostHog events, get_current_user hardening), `app/__init__.py` (Sentry, PostHog sync_mode, ProxyFix, session hardening, Linear client_secret_post), `app/static/css/style.css` (sidebar positioning, mobile responsiveness, footer grid, logo consistency), `app/templates/dashboard.html` (thinking overlay, logo, mobile layout), `app/templates/connect.html` (bot-invite callout card), `Procfile` (--timeout 60), `requirements.txt` (google-genai, posthog, openai, sentry-sdk additions).

**Action for next session:** re-pull the live repo and diff against this list before assuming any item above is actually deployed — several fixes were discussed in conversation but, per this consolidation pass, at least two were never applied to the actual code.
