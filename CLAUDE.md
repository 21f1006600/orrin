# Orrin — Project Memory

> This file is the single source of truth for Orrin's context. Paste this entire file at the start of any new conversation about this project so the AI has full context without re-explaining everything.

---

## What Orrin Is

Orrin is an AI operational-intelligence tool for early-stage startups. It connects to Slack and Linear, indexes messages and tickets, and answers plain-English questions like "why is the onboarding redesign delayed?" with a synthesized answer, a confidence score, and cited sources.

**One-liner:** Ask your company anything. Orrin connects Slack and Linear so founders get instant, evidence-backed answers instead of searching through conversations and tickets.

**YC alignment:** Matches YC Summer 2026 RFS category "Company Brain" — extracting scattered company knowledge into a living map of how a company works.

**V1 scope (deliberately limited):** Answer operational questions from synced Slack/Linear data with sources. V1 does NOT create tickets, send reminders, automate workflows, generate reports, manage projects, or act as a general chatbot.

---

## Founder Context

- First-time solo founder, fresher graduating Sep 2026
- AI/ML background; prior projects: multi-agent research engine, fare prediction, Quiz Master (Flask/Jinja/SQLite)
- Not deeply experienced in MERN/MEAN/TypeScript — builds with Flask, AI-assisted coding (Cursor), and strong product instincts (PRDs, wireframes, user research)
- Targeting YC W27 application (~Oct 2026), ~40-day build window from project start
- Zero/near-zero budget — every tool choice has been filtered through "is this free or near-free"

---

## Product Identity

- **Name:** Orrin (originally explored: Company Brain, Kerno, Fathom, Clarix, Lumin, Operis — all taken or rejected; Orrin chosen, domain available)
- **Domain:** getorrin.xyz (purchased via Namecheap), live at **https://www.getorrin.xyz**
- **Logo:** Three coral/salmon triangles forming an abstract "M"/mountain shape on deep purple, paired with lowercase "orrin" wordmark. Saved as `orrin-logo.png` in `app/static/`. Favicon set fully implemented (favicon.ico, 16x16, 32x32, apple-touch-icon, site.webmanifest).
- **Design language:** Dark theme, near-black background (#0b0d12), refined blue accent (#4f7df9), Geist font (matching v0.dev reference design), card-based UI with subtle borders (#22252e).
- **Design reference:** Built using v0.dev-generated wireframes/screenshots as the visual source of truth — landing page, onboarding flow, dashboard ("Ask Orrin"), Command Center, Company Memory timeline (the latter two are V2, not built yet).

---

## Tech Stack

- **Backend:** Python + Flask (Blueprint pattern, `app/routes.py`)
- **Database:** SQLite locally (`orrin.db`), Postgres in production (Railway-provisioned, via `DATABASE_URL`, auto-detected with fallback to SQLite if absent)
- **ORM:** Flask-SQLAlchemy
- **Auth:** Authlib for OAuth (Google, Slack, Linear), Flask session-based
- **AI:** Google Gemini — `google-genai` SDK (NOT the deprecated `google-generativeai`), model `gemini-2.5-flash-lite` (free tier as of mid-2026)
- **Frontend:** Server-rendered Jinja2 templates, hand-written external CSS (no Tailwind, no CSS framework) in `app/static/css/style.css`
- **Templating pattern:** `layout.html` is the base template (navbar, footer, head) that marketing/auth pages extend via `{% extends "layout.html" %}`. `dashboard.html` is intentionally standalone (own html/head/body) because it has a sidebar layout incompatible with the marketing navbar/footer.
- **Security:** Flask-Limiter (rate limiting, in-memory store), Flask-WTF (CSRF), session hardening (HttpOnly, SameSite=Lax, Secure in production, 24h expiry)
- **Monitoring:** Sentry (active only when FLASK_ENV=production and SENTRY_DSN is set). Custom logger writes to orrin.log + console for business events: signups, logins, connections, questions asked.
- **Deployment:** Railway (web service + Postgres), Procfile (web: gunicorn run:app), requirements.txt
- **Proxy handling:** ProxyFix middleware (Werkzeug) is required — Railway terminates HTTPS at the proxy and forwards HTTP internally; without ProxyFix, Flask generates http:// OAuth redirect URLs in production, breaking OAuth callbacks.

---

## Database Schema (app/models.py)

- **User** — id, email, name, picture, slack_team_id, slack_team_name, slack_bot_token, linear_access_token, linear_workspace_name, last_synced_at (used for auto-sync throttling)
- **SlackMessage** — id, user_id (FK), channel_id, channel_name, message_text, author, posted_at, synced_at
- **LinearIssue** — id, user_id (FK), issue_identifier, title, description, status, assignee, updated_at, synced_at

---

## Core Files Map

```
orrin/
├── app/
│   ├── __init__.py          # App factory, OAuth registration, Sentry, ProxyFix, rate limiter, CSRF
│   ├── routes.py            # All routes (Blueprint main), get_current_user() IDOR-safe helper
│   ├── models.py            # User, SlackMessage, LinearIssue
│   ├── sync.py              # sync_slack_data(), sync_linear_data() - real API calls, name resolution, dedup
│   ├── ai.py                # MOCK_MODE flag, build_context(), ask_orrin(), Gemini client, retry logic
│   ├── templates/
│   │   ├── layout.html      # Base template - navbar (session-aware sign in/log out), footer
│   │   ├── index.html       # Landing page (extends layout)
│   │   ├── login.html       # Google sign-in card (extends layout)
│   │   ├── connect.html     # Slack/Linear connection cards, allows proceeding with just ONE tool
│   │   └── dashboard.html   # Standalone - sidebar + Ask Orrin interface + answer view + thinking overlay
│   └── static/
│       ├── css/style.css    # All styles, hand-written, no framework
│       └── orrin-logo.png, favicon set
├── requirements.txt
├── Procfile
├── run.py                   # create_app() + db.create_all()
└── .env / .gitignore         # Never committed; verified clean via git log scan
```

---

## Key Architectural Decisions (and why)

1. **IDOR safety:** get_current_user() is the ONLY way routes should fetch the logged-in user - it derives identity strictly from session['user_email'], never from request parameters. It also auto-clears stale sessions if the session points to a user that no longer exists in the DB (e.g., after a database reset).

2. **Single-tool onboarding:** Originally required BOTH Slack and Linear connected before reaching the dashboard. Changed deliberately - users can now proceed with just one connected tool, since forcing both blocked adoption for teams that only use one.

3. **Auto-sync before answering:** Originally sync was manual-only (/sync route). This caused a real bug - fresh Slack messages weren't visible to the AI until someone remembered to manually sync. Fixed by auto-syncing inline before every question, throttled to once per 60 seconds via last_synced_at to avoid redundant syncs on rapid follow-up questions.

4. **Mock mode for free testing:** ai.py has a MOCK_MODE boolean. When True, a rule-based mock answer generator runs on REAL synced data (no API calls, $0 cost). Currently set to False (real Gemini is live in production).

5. **Why Gemini over Claude:** Claude Sonnet is roughly 30x more expensive per token than Gemini 2.5 Flash-Lite. At this stage (zero revenue, budget-constrained), Gemini's free tier (1,500 req/day) is the right call. Revisit Claude once there's revenue or funding.

6. **Why google-genai not google-generativeai:** The latter is officially deprecated/sunset and was causing a DefaultCredentialsError in production due to internal credential-discovery bugs - NOT a wrong API key. Migrated fully to the new SDK.

7. **Gemini API key format change:** As of ~June 2026, Google migrated key formats from AIzaSy... (Standard) to AQ.Ab... (Auth keys, bound to a service account). Standard keys are being rejected industry-wide starting June 19 2026, fully rejected by September 2026. A key starting with AQ. is CORRECT, not a mistake.

8. **Retry logic for Gemini 503s:** Gemini's free tier occasionally returns 503 UNAVAILABLE (server overload, not a code bug). ask_orrin() retries up to 3 times with exponential backoff. If all retries fail, the dashboard shows a "Try again" button that resubmits the same question with one click.

9. **Why mock-mode logic checks OR not AND for empty data:** The "no data" fallback message only triggers if BOTH Slack and Linear are empty - supports the single-tool onboarding decision above.

---

## Known Issues / Open Threads (as of last session)

1. **ACTIVE BUG - Slack sync appears channel-scoped in practice.** A message posted in #social was not found by Orrin even after auto-sync, while messages in #orrin-dev work fine. Leading hypothesis: the Orrin Slack bot was never explicitly invited to #social via /invite @Orrin - Slack bots can only read channels they've been added to, regardless of OAuth scopes granted. Next step: check #social member list in Slack for the Orrin bot; if missing, /invite @Orrin there and retest. If the bot IS already a member and it still fails, this becomes a real sync bug worth deeper investigation.

2. **Rate limiting uses in-memory storage**, not Redis. Acceptable at current scale but means limits reset on every redeploy and don't share state across multiple workers/instances. Revisit with Redis once real concurrent traffic exists.

3. **Context window ceiling:** build_context() in ai.py pulls the 100 most recent Slack messages and 50 most recent Linear issues, ordered by recency, across ALL connected channels combined. At current low usage this covers everything, but as real usage grows, older messages will silently fall outside this window.

4. **Railway custom domain limit:** Free/current plan only allows one custom domain. www.getorrin.xyz is live and verified; the bare getorrin.xyz (no www) uses a Namecheap URL-redirect instead of a separate Railway domain.

5. **Mixpanel/product analytics - deliberately deferred.** Structured logging already captures core "who did what" events. Revisit dedicated analytics once there are enough real users.

---

## OAuth Apps Reference

- **Google Cloud project:** "Orrin" - OAuth consent screen External, test users added. Redirect URIs registered for both localhost and the live domain.
- **Slack app:** "Orrin," developed under workspace OrrinDev (a dedicated clean test workspace - the original attempt under workspace "Ignitus" failed because that workspace had hit its 10-app free-tier limit; a second attempt also failed because the app was created tied to Ignitus and apps cannot be moved between workspaces after creation - had to delete and recreate fresh under OrrinDev). Bot Token Scopes: channels:history, channels:read, groups:read, groups:history, users:read.
- **Linear OAuth app:** "Orrin," created at linear.app/settings/api. Note: the "Developer URL" field rejected http://localhost:5000 - workaround was using https://localhost:5000 or a placeholder (cosmetic field only).
- **Gemini API key:** From Google AI Studio (aistudio.google.com), NOT Google Cloud Console directly. Current format starts with AQ. - this is correct per the 2026 key migration.

---

## Environment Variables Required

```
GOOGLE_CLIENT_ID
GOOGLE_CLIENT_SECRET
SLACK_CLIENT_ID
SLACK_CLIENT_SECRET
LINEAR_CLIENT_ID
LINEAR_CLIENT_SECRET
GEMINI_API_KEY
SECRET_KEY
SENTRY_DSN
FLASK_ENV=production
```

App refuses to start without SECRET_KEY. ai.py refuses to start without GEMINI_API_KEY when MOCK_MODE = False.

---

## Deployment Checklist Status

1. Fixed dead Gemini model name and migrated SDK - DONE
2. Switched SQLite to Postgres-capable - DONE
3. Deployed to Railway, live at custom domain - DONE
4. Updated OAuth redirect URLs for production domain - DONE
5. Production env vars set - DONE

Status: genuinely deployed and working in production, including real AI answers with correct source citation, confirmed via live testing.

---

## What's Next

1. Fix the #social channel sync issue (see Known Issues #1)
2. Get 2-3 real strangers (not friends) to test the live product
3. Watch what real users actually ask
4. Resume security hardening only as needed (Redis-backed rate limiting once real concurrent traffic exists)
5. Eventually: write the YC application using real usage evidence

---

## Things NOT to re-litigate

- The idea is Orrin (Company Brain for startups). Do not reopen comparisons to healthcare/finance/dev-tools alternative ideas.
- The name is Orrin, domain getorrin.xyz.
- The AI provider is Gemini (google-genai SDK), not Claude.
- Mock mode exists for free testing but is currently OFF - real AI is live.
